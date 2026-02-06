"""
Обработка действий детей: подтверждение выполнения заданий и отправка медиа.
См. SPEC.md раздел 5 "Выдача задач и подтверждение выполнения"
"""
import logging

from aiogram import Router, Bot
from aiogram.types import CallbackQuery, Message, ForceReply
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.keyboards.callbacks import TASK_COMPLETE
from bot.config import ADMIN_TELEGRAM_ID
from bot.services.media_service import MediaService
from bot.services.task_service import TaskService
from bot.utils.auto_delete import schedule_message_delete
from bot.utils.event_log import log_event
from db.database import AsyncSessionLocal
from db.models import Task, TaskStatus

router = Router()

# Настройка логирования
logger = logging.getLogger(__name__)


async def notify_admin_about_completion(bot: Bot, task: Task, child_name: str, has_media: bool = False):
    """Уведомление администратора/родителя о выполнении задания"""
    if not ADMIN_TELEGRAM_ID:
        return

    try:
        notify_parent = getattr(task.task_type, "notify_on_completion", False)
        if notify_parent:
            await bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID,
                text=f"🔔 Ребёнок {child_name} выполнил задание «{task.task_type.name}» только что."
            )
        else:
            media_text = " (с отчетом)" if has_media else ""
            await bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID,
                text=f"✅ Задание выполнено!\n\n"
                     f"👦 Ребенок: {child_name}\n"
                     f"📋 Задание: {task.task_type.name}\n"
                     f"💰 Награда: {task.reward_amount} ARS{media_text}"
            )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


@router.callback_query(lambda c: c.data == TASK_COMPLETE)
async def handle_task_complete_callback(callback: CallbackQuery):
    """
    Обработка нажатия кнопки "✅ Выполнил"
    """
    message_id = callback.message.message_id
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    logger.info(f"Task complete callback received: message_id={message_id}, chat_id={chat_id}, user_id={user_id}")
    
    try:
        async with AsyncSessionLocal() as session:
            task = await TaskService.get_pending_task_by_message(session, chat_id, message_id)
            if not task:
                logger.warning(f"Task not found for message_id={message_id}, chat_id={chat_id}")
                await callback.answer("Задание не найдено или уже выполнено", show_alert=True)
                return

            if task.child.telegram_user_id is not None and callback.from_user.id != task.child.telegram_user_id:
                await callback.answer("Это задание назначено другому пользователю.", show_alert=True)
                return

            if task.task_type.requires_media:
                existing_media_list = await MediaService.get_task_media(session, task.id)
                if existing_media_list:
                    await TaskService.mark_task_as_done(session, task.id)
                    log_event(f'Ребёнок {task.child.display_name} выполнил задание "{task.task_type.name}"')
                    logger.info(
                        "task_completed: task_id=%s, child=%s, task_type=%s",
                        task.id, task.child.display_name, task.task_type.name,
                    )
                    await callback.answer("✅ Задание отмечено как выполненное!")
                    done_msg = await callback.message.reply("✅ Готово")
                    schedule_message_delete(callback.bot, callback.message.chat.id, done_msg.message_id, 15)
                    child_name = task.child.display_name or "Ребенок"
                    await notify_admin_about_completion(callback.bot, task, child_name, has_media=True)
                else:
                    prompt_msg = await callback.message.answer(
                        "📸 Ответь на задание выполнением\n"
                        "(отправь фото или скриншот в ответ на это сообщение)",
                        reply_markup=ForceReply(selective=True)
                    )
                    task.prompt_message_id = prompt_msg.message_id
                    await session.commit()
                    await callback.answer()
            else:
                await TaskService.mark_task_as_done(session, task.id)
                log_event(f'Ребёнок {task.child.display_name} выполнил задание "{task.task_type.name}"')
                logger.info(
                    "task_completed: task_id=%s, child=%s, task_type=%s",
                    task.id, task.child.display_name, task.task_type.name,
                )
                await callback.answer("✅ Задание отмечено как выполненное!")
                done_msg = await callback.message.reply("✅ Готово")
                schedule_message_delete(callback.bot, callback.message.chat.id, done_msg.message_id, 15)
                child_name = task.child.display_name or "Ребенок"
                await notify_admin_about_completion(callback.bot, task, child_name, has_media=False)

    except Exception as e:
        logger.error(f"Error handling task completion: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке выполнения", show_alert=True)


@router.message(lambda m: m.reply_to_message and not (m.photo or m.video or m.document))
async def handle_text_reply_to_task(message: Message):
    """
    Обработка ответа текстом (или другим не-медиа) на задание с requires_media.
    Повторяем запрос на скриншот/фото.
    """
    reply_message_id = message.reply_to_message.message_id
    chat_id = message.chat.id

    try:
        async with AsyncSessionLocal() as session:
            task = await TaskService.get_pending_task_by_reply(
                session, chat_id, reply_message_id
            )
            if not task or not task.task_type.requires_media:
                return

            if task.child.telegram_user_id is not None and message.from_user.id != task.child.telegram_user_id:
                await message.answer("Это задание назначено другому пользователю.")
                return

            reminder_msg = await message.answer(
                "📸 В качестве подтверждения выполнения задания нужен скриншот или фото. "
                "Пожалуйста, пришли фото или скриншот ответом на сообщение с заданием."
            )
            task.reminder_message_id = reminder_msg.message_id
            await session.commit()
    except Exception as e:
        logger.error(f"Error handling text reply to task: {e}", exc_info=True)


@router.message(lambda m: m.photo or m.video or m.document)
async def handle_media(message: Message):
    """
    Обработка медиа (фото/видео/документы) от детей
    """
    chat_id = message.chat.id
    reply_message_id = message.reply_to_message.message_id if message.reply_to_message else None

    if not message.reply_to_message:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Task)
                    .options(selectinload(Task.task_type), selectinload(Task.child))
                    .where(
                        Task.chat_id == chat_id,
                        Task.status == TaskStatus.PENDING
                    )
                    .order_by(Task.created_at.desc())
                    .limit(1)
                )
                task = result.scalar_one_or_none()
                if task and task.task_type.requires_media:
                    if task.child.telegram_user_id is not None and message.from_user.id != task.child.telegram_user_id:
                        return
                    reminder_msg = await message.answer(
                        "📸 Ответьте фото или скриншотом на сообщение с заданием "
                        "(нажмите на сообщение с кнопкой «Выполнил» и выберите «Ответить»)."
                    )
                    task.reminder_message_id = reminder_msg.message_id
                    await session.commit()
        except Exception as e:
            logger.error(f"Error handling media without reply: {e}", exc_info=True)
        return

    try:
        async with AsyncSessionLocal() as session:
            task = await TaskService.get_pending_task_by_reply(
                session, chat_id, reply_message_id
            )
            if not task:
                return

            if task.child.telegram_user_id is not None and message.from_user.id != task.child.telegram_user_id:
                await message.answer("Это задание назначено другому пользователю.")
                return

            if not task.task_type.requires_media:
                await message.answer("Для этого задания не требуется прикреплять медиа.")
                return

            await MediaService.save_task_media(session, task, message)
            log_event(f'Ребёнок {task.child.display_name} выполнил задание "{task.task_type.name}"')
            logger.info(
                "task_completed: task_id=%s, child=%s, task_type=%s (with media)",
                task.id, task.child.display_name, task.task_type.name,
            )
            done_msg = await message.answer("✅ Готово")
            schedule_message_delete(message.bot, message.chat.id, done_msg.message_id, 15)
            child_name = task.child.display_name or "Ребенок"
            await notify_admin_about_completion(message.bot, task, child_name, has_media=True)

    except Exception as e:
        logger.error(f"Error handling media: {e}", exc_info=True)
        await message.answer("Произошла ошибка при сохранении отчета.")


