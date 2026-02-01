"""
Сервис для обработки медиа по заданиям.
См. SPEC.md раздел 5.3 "Обработка медиа"
"""
from aiogram.types import Message as TelegramMessage

from db.models import MediaFileType, Task, TaskMedia
from sqlalchemy.ext.asyncio import AsyncSession


class MediaService:
    """Сервис для работы с медиа"""

    @staticmethod
    async def save_task_media(
        session: AsyncSession,
        task: Task,
        telegram_message: TelegramMessage,
    ) -> TaskMedia:
        """
        Сохранение медиа для задачи.
        См. SPEC.md раздел 5.3, шаг 3:
        - Сохранение task_media с telegram_file_id
        - Обновление статуса задачи (если требуется)
        """
        # Определяем тип файла и file_id
        file_id = None
        file_type = None

        if telegram_message.photo:
            file_id = telegram_message.photo[-1].file_id  # Берём фото максимального размера
            file_type = MediaFileType.PHOTO
        elif telegram_message.video:
            file_id = telegram_message.video.file_id
            file_type = MediaFileType.VIDEO
        elif telegram_message.document:
            file_id = telegram_message.document.file_id
            file_type = MediaFileType.DOCUMENT

        if not file_id or not file_type:
            raise ValueError("Сообщение не содержит поддерживаемого типа медиа")

        # Создание записи task_media
        task_media = TaskMedia(
            task_id=task.id,
            telegram_file_id=file_id,
            file_type=file_type,
        )
        session.add(task_media)

        # Если задача ещё не выполнена, отмечаем её как выполненную
        # (медиа приходит после нажатия кнопки "✅ Выполнил")
        if task.status.value == "pending":
            from datetime import datetime

            from db.models import TaskStatus

            task.status = TaskStatus.DONE
            task.completed_at = datetime.utcnow()

        await session.commit()
        await session.refresh(task_media)
        return task_media

    @staticmethod
    async def get_task_media(session: AsyncSession, task_id: int) -> list[TaskMedia]:
        """Получение всех медиа для задачи"""
        from sqlalchemy import select

        result = await session.execute(
            select(TaskMedia).where(TaskMedia.task_id == task_id)
        )
        return list(result.scalars().all())



