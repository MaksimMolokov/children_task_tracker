"""
Общие команды бота (start, help).
См. SPEC.md раздел 4.1 "Регистрация и роли"
"""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User, UserRole

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Команда /start
    Проверяет роль пользователя в базе данных и показывает соответствующее меню:
    - ADMIN: админ-меню
    - CHILD: приветствие для ребенка
    - Не зарегистрирован: сообщение о регистрации
    """
    async with AsyncSessionLocal() as session:
        user_id = message.from_user.id
        logger.info(f"Получен /start от пользователя ID: {user_id}")
        
        # Проверяем, есть ли пользователь в базе данных
        result = await session.execute(
            select(User).where(
                User.telegram_user_id == user_id,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()

        if user:
            # Пользователь найден в БД
            if user.role == UserRole.ADMIN:
                # Администратор
                from bot.keyboards.admin import get_admin_main_menu
                from bot.handlers.admin_menu import format_admin_guide

                await message.answer(
                    "Добро пожаловать, администратор!\n\n"
                    "⚠️ Важно: для работы бота его нужно добавить в чат, где будут происходить выдача заданий, "
                    "и сделать администратором этого чата.\n\n"
                    "Используйте /admin для входа в админ-панель.",
                    reply_markup=get_admin_main_menu(),
                )
                guide_text = format_admin_guide()
                await message.answer(guide_text)
            elif user.role == UserRole.CHILD:
                # Ребенок
                await message.answer(
                    f"Привет, {user.display_name}!\n\n"
                    "Я бот для контроля выполнения заданий.\n"
                    "Твои задания будут приходить сюда. "
                    "Выполняй их и получай награды!"
                )
            else:
                # Неизвестная роль
                await message.answer(
                    "Привет! Я бот для контроля выполнения заданий. "
                    "Обратитесь к администратору для регистрации."
                )
        else:
            # Пользователь не найден в БД
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

