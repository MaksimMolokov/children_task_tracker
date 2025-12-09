"""
Обработка действий детей: подтверждение выполнения заданий и отправка медиа.
См. SPEC.md раздел 5 "Выдача задач и подтверждение выполнения"
"""
from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.keyboards.inline import get_task_completion_keyboard
from db.database import AsyncSessionLocal
from db.models import MediaFileType, Task, TaskStatus

router = Router()

# Добавляем логирование для отладки
import logging
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data == "task_complete")
async def handle_task_complete_callback(callback: CallbackQuery):
    """
    Обработка нажатия кнопки "✅ Выполнил"
    См. SPEC.md раздел 5.2 "Обработка нажатия '✅ Выполнил'"
    
    Шаги:
    1. Находим task по chat_id + message_id
    2. Проверяем status = pending
    3. Если requires_media = false -> статус = done
    4. Если requires_media = true -> проверяем наличие медиа
    """
    message_id = callback.message.message_id
    chat_id = callback.message.chat.id
    
    logger.info(f"Task complete callback received: message_id={message_id}, chat_id={chat_id}, user_id={callback.from_user.id}")
    
    async with AsyncSessionLocal() as session:
        # Находим задание по message_id и chat_id
        result = await session.execute(
            select(Task).where(
                Task.message_id == message_id,
                Task.chat_id == chat_id,
                Task.status == TaskStatus.PENDING
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            # Попробуем найти задание без проверки статуса для отладки
            result_all = await session.execute(
                select(Task).where(
                    Task.message_id == message_id,
                    Task.chat_id == chat_id
                )
            )
            task_all = result_all.scalar_one_or_none()
            if task_all:
                logger.warning(f"Task found but status is {task_all.status}, not PENDING")
            else:
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
                await callback.message.reply("🎉 Отлично! Задание выполнено и проверено!")
            else:
                # Медиа нет, просим отправить
                await callback.answer(
                    "📸 Для завершения задания нужно приложить фото или видео.\n"
                    "Отправьте фото или видео ответом на это сообщение (нажмите на сообщение и выберите 'Ответить').",
                    show_alert=True
                )
        else:
            # Отчет не требуется, сразу отмечаем как выполненное
            task.status = TaskStatus.DONE
            task.completed_at = datetime.utcnow()
            await session.commit()
            await callback.answer("✅ Задание отмечено как выполненное!")
            await callback.message.reply("🎉 Отлично! Задание выполнено!")


@router.message(lambda m: m.photo or m.video or m.document)
async def handle_media(message: Message):
    """
    Обработка медиа (фото/видео/документы) от детей
    См. SPEC.md раздел 5.3 "Обработка медиа"
    
    Шаги:
    1. Проверяем, что это reply на сообщение с заданием
    2. Находим задание по message_id и chat_id
    3. Проверяем, что требуется медиа и задание в статусе PENDING
    4. Сохраняем task_media и обновляем статус задачи
    """
    if not message.reply_to_message:
        await message.answer(
            "Пожалуйста, отправьте медиа ответом на сообщение с заданием "
            "(нажмите на сообщение и выберите 'Ответить')."
        )
        return
    
    reply_message_id = message.reply_to_message.message_id
    chat_id = message.chat.id
    
    async with AsyncSessionLocal() as session:
        # Находим задание по message_id и chat_id
        result = await session.execute(
            select(Task).where(
                Task.message_id == reply_message_id,
                Task.chat_id == chat_id,
                Task.status == TaskStatus.PENDING
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            await message.answer("Задание не найдено или уже выполнено.")
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
        
        await message.answer("✅ Медиа получено! Задание отмечено как выполненное! 🎉")


