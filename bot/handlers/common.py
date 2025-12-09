"""
Общие команды бота (start, help).
См. SPEC.md раздел 4.1 "Регистрация и роли"
"""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import ADMIN_TELEGRAM_ID
from db.database import AsyncSessionLocal
from db.models import User, UserRole

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Команда /start
    См. SPEC.md раздел 4.1:
    - При /start от админа (по ADMIN_TELEGRAM_ID) помечает его как admin
    - Для остальных пользователей - обычное приветствие
    """
    from db.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # Проверка, является ли пользователь админом
        # Отладочная информация (можно удалить позже)
        logger = logging.getLogger(__name__)
        logger.info(f"Получен /start от пользователя ID: {message.from_user.id}, ожидаемый ADMIN_ID: {ADMIN_TELEGRAM_ID}")
        
        if message.from_user.id == ADMIN_TELEGRAM_ID:
            # Проверка/создание записи админа в БД
            from sqlalchemy import select

            result = await session.execute(
                select(User).where(User.telegram_user_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    telegram_user_id=message.from_user.id,
                    role=UserRole.ADMIN,
                    display_name="Админ",
                )
                session.add(user)
                await session.commit()
                from bot.keyboards.admin import get_admin_main_menu
                from bot.handlers.admin_menu import format_admin_guide

                await message.answer(
                    "Добро пожаловать, администратор!\n\n"
                    "⚠️ **Важно:** для работы бота его нужно добавить в чат, где будут происходить выдача заданий, "
                    "и сделать администратором этого чата.\n\n"
                    "Используйте /admin для входа в админ-панель.",
                    reply_markup=get_admin_main_menu(),
                )
                guide_text = format_admin_guide()
                await message.answer(guide_text)
            else:
                from bot.keyboards.admin import get_admin_main_menu
                from bot.handlers.admin_menu import format_admin_guide

                await message.answer(
                    "Вы уже зарегистрированы как администратор.\n\n"
                    "⚠️ Не забудьте: бота нужно добавить в чат для выдачи заданий и сделать администратором.\n\n"
                    "Используйте /admin для входа в админ-панель.",
                    reply_markup=get_admin_main_menu(),
                )
        else:
            await message.answer(
                "Привет! Я бот для контроля выполнения заданий. "
                "Обратитесь к администратору для регистрации."
            )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help - показывает список доступных команд"""
    # TODO: Реализовать динамический список команд в зависимости от роли пользователя
    await message.answer(
        "Доступные команды:\n"
        "/start - Регистрация\n"
        "/help - Список команд"
    )

