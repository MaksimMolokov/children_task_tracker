"""
Middleware для проверки прав доступа пользователей.
См. SPEC.md раздел 4.1 "Регистрация и роли"
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User, UserRole


async def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором через БД"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_user_id == user_id,
                User.role == UserRole.ADMIN,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()
        return user is not None


class AdminMiddleware(BaseMiddleware):
    """Middleware для проверки, является ли пользователь администратором"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if user_id is None:
            return
        
        # Проверка через БД
        if not await is_admin(user_id):
            if isinstance(event, Message):
                await event.answer("Эта команда доступна только администратору.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Эта команда доступна только администратору.", show_alert=True)
            return
        return await handler(event, data)



