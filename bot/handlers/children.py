"""
Обработка действий детей: подтверждение выполнения заданий и отправка медиа.
См. SPEC.md раздел 5 "Выдача задач и подтверждение выполнения"
"""
from datetime import datetime
import logging

from aiogram import Router, Bot
from aiogram.types import CallbackQuery, Message, ForceReply
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from bot.keyboards.inline import get_task_completion_keyboard
from bot.config import ADMIN_TELEGRAM_ID
from db.database import AsyncSessionLocal
from db.models import MediaFileType, Task, TaskStatus, User

router = Router()

# Настройка логирования
logger = logging.getLogger(__name__)


async def notify_admin_about_completion(bot: Bot, task: Task, child_name: str, has_media: bool = False):
    """Уведомление администратора о выполнении задания"""
    if not ADMIN_TELEGRAM_ID:
        return

    try:
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


@router.callback_query(lambda c: c.data == "task_complete")
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
            # Находим задание по message_id и chat_id
            # Используем chat_id, но если он 0 или None, пробуем найти только по message_id (менее надежно, но как фолбэк)
            query = select(Task).options(selectinload(Task.task_type), selectinload(Task.child)).where(
                Task.message_id == message_id,
                Task.status == TaskStatus.PENDING
            )
            
            if chat_id:
                query = query.where(Task.chat_id == chat_id)
                
            result = await session.execute(query)
            task = result.scalar_one_or_none()
            
            if not task:
                logger.warning(f"Task not found for message_id={message_id}, chat_id={chat_id}")
                await callback.answer("Задание не найдено или уже выполнено", show_alert=True)
                return
            
            # Проверяем, требуется ли отчет
            if task.task_type.requires_media:
                # Проверяем, есть ли уже медиа для этого задания
                from db.models import TaskMedia
                media_result = await session.execute(
                    select(TaskMedia).where(TaskMedia.task_id == task.id)
                )
                existing_media = media_result.scalar_one_or_none()
                
                if existing_media:
                    # Медиа уже есть, отмечаем задание как выполненное
                    task.status = TaskStatus.DONE
                    task.completed_at = datetime.utcnow()
                    await session.commit()
                    
                    await callback.answer("✅ Задание отмечено как выполненное!")
                    await callback.message.reply("✅ Готово")
                    
                    # Уведомляем админа
                    child_name = task.child.display_name or "Ребенок"
                    await notify_admin_about_completion(callback.bot, task, child_name, has_media=True)
                else:
                    # Медиа нет, просим отправить сообщение
                    prompt_msg = await callback.message.answer(
                        "📸 Ответь на задание выполнением\n"
                        "(отправь фото или скриншот в ответ на это сообщение)",
                        reply_markup=ForceReply(selective=True)
                    )
                    
                    # Сохраняем ID сообщения-промпта
                    task.prompt_message_id = prompt_msg.message_id
                    await session.commit()
                    
                    await callback.answer()
            else:
                # Отчет не требуется, сразу отмечаем как выполненное
                task.status = TaskStatus.DONE
                task.completed_at = datetime.utcnow()
                await session.commit()
                
                await callback.answer("✅ Задание отмечено как выполненное!")
                await callback.message.reply("✅ Готово")
                
                # Уведомляем админа
                child_name = task.child.display_name or "Ребенок"
                await notify_admin_about_completion(callback.bot, task, child_name, has_media=False)

    except Exception as e:
        logger.error(f"Error handling task completion: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке выполнения", show_alert=True)


@router.message(lambda m: m.photo or m.video or m.document)
async def handle_media(message: Message):
    """
    Обработка медиа (фото/видео/документы) от детей
    """
    if not message.reply_to_message:
        await message.answer(
            "Пожалуйста, отправьте медиа ответом на сообщение с заданием "
            "(нажмите на сообщение и выберите 'Ответить')."
        )
        return
    
    reply_message_id = message.reply_to_message.message_id
    chat_id = message.chat.id
    
    try:
        async with AsyncSessionLocal() as session:
            # Находим задание по message_id (оригинальное) или prompt_message_id (просьба отчета)
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.task_type), selectinload(Task.child))
                .where(
                    or_(
                        Task.message_id == reply_message_id,
                        Task.prompt_message_id == reply_message_id
                    ),
                    Task.chat_id == chat_id,
                    Task.status == TaskStatus.PENDING
                )
            )
            task = result.scalar_one_or_none()
            
            if not task:
                # Если задача не найдена, возможно она уже выполнена или это не ответ на задачу
                # Не будем спамить, если это просто фото в чате
                return
            
            # Проверяем, требуется ли медиа для этого задания
            if not task.task_type.requires_media:
                await message.answer("Для этого задания не требуется прикреплять медиа.")
                return
            
            # Определяем тип медиа и file_id
            telegram_file_id = None
            file_type = None
            
            if message.photo:
                # Берем фото с самым большим разрешением
                telegram_file_id = message.photo[-1].file_id
                file_type = MediaFileType.PHOTO
            elif message.video:
                telegram_file_id = message.video.file_id
                file_type = MediaFileType.VIDEO
            elif message.document:
                telegram_file_id = message.document.file_id
                file_type = MediaFileType.DOCUMENT
            else:
                await message.answer("Поддерживаются только фото, видео или документы.")
                return
            
            # Сохраняем медиа
            from db.models import TaskMedia
            task_media = TaskMedia(
                task_id=task.id,
                telegram_file_id=telegram_file_id,
                file_type=file_type
            )
            session.add(task_media)
            
            # Обновляем статус задания
            task.status = TaskStatus.DONE
            task.completed_at = datetime.utcnow()
            
            await session.commit()
            
            await message.answer("✅ Готово")
            
            # Уведомляем админа
            child_name = task.child.display_name or "Ребенок"
            await notify_admin_about_completion(message.bot, task, child_name, has_media=True)

    except Exception as e:
        logger.error(f"Error handling media: {e}", exc_info=True)
        await message.answer("Произошла ошибка при сохранении отчета.")


