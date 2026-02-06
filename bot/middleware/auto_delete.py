"""
Удаление сообщений пользователя через 60 секунд после отправки.

Отличие от bot.utils.auto_delete.schedule_message_delete:
- здесь удаляются сообщения пользователя (не бота) по таймеру;
- schedule_message_delete — отложенное удаление конкретного сообщения бота (ответы, отчёты).
"""
import asyncio
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class AutoDeleteMiddleware(BaseMiddleware):
    """Удаление сообщений пользователя через 60 сек после отправки (не сообщений бота)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        result = await handler(event, data)

        # Если это сообщение от пользователя (не от бота), удаляем через 1 минуту
        if isinstance(event, Message) and event.from_user and not event.from_user.is_bot:
            # Создаём задачу на удаление через 60 секунд
            async def delete_message():
                await asyncio.sleep(60)  # Ждём 1 минуту
                try:
                    await event.delete()
                except Exception:
                    # Сообщение уже удалено или нет прав - игнорируем
                    pass

            # Запускаем задачу в фоне
            asyncio.create_task(delete_message())

        return result


