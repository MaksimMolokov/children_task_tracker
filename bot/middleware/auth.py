"""
Middleware для проверки прав доступа пользователей.
См. SPEC.md раздел 4.1 "Регистрация и роли"
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import ADMIN_TELEGRAM_ID


class AdminMiddleware(BaseMiddleware):
    """Middleware для проверки, является ли пользователь администратором"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.from_user.id != ADMIN_TELEGRAM_ID:
                await event.answer("Эта команда доступна только администратору.")
                return
        elif isinstance(event, CallbackQuery):
            # Для CallbackQuery нужно проверить через event.from_user
            if event.from_user.id != ADMIN_TELEGRAM_ID:
                await event.answer("Эта команда доступна только администратору.", show_alert=True)
                return
        return await handler(event, data)



