"""
Общие команды бота (start, help, feedback).
См. SPEC.md раздел 4.1 "Регистрация и роли"
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from bot.handlers.fsm_states import FeedbackStates
from bot.utils.auto_delete import schedule_message_delete
from db.database import AsyncSessionLocal
from db.models import Feedback, User, UserRole

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
                # Администратор: показываем постоянную клавиатуру внизу
                from bot.keyboards.admin import get_admin_reply_keyboard
                from bot.handlers.admin_menu import format_admin_guide

                await message.answer(
                    "Добро пожаловать, администратор!\n\n"
                    "Используйте кнопки ниже для управления ботом.",
                    reply_markup=get_admin_reply_keyboard(),
                )
                guide_text = format_admin_guide()
                guide_msg = await message.answer(guide_text)
                schedule_message_delete(message.bot, message.chat.id, guide_msg.message_id)
            elif user.role == UserRole.CHILD:
                # Ребенок
                child_msg = await message.answer(
                    f"Привет, {user.display_name}!\n\n"
                    "Я бот для контроля выполнения заданий.\n"
                    "Твои задания будут приходить сюда. "
                    "Выполняй их и получай награды!"
                )
                schedule_message_delete(message.bot, message.chat.id, child_msg.message_id)
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
    """Команда /help — список команд в зависимости от роли пользователя"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_user_id == message.from_user.id,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()

        if user:
            if user.role == UserRole.ADMIN:
                help_msg = await message.answer(
                    "Доступные команды:\n"
                    "/start — перезапуск и меню\n"
                    "/admin — вход в админ-панель\n"
                    "/help — этот список команд"
                )
                schedule_message_delete(message.bot, message.chat.id, help_msg.message_id)
            elif user.role == UserRole.CHILD:
                help_msg = await message.answer(
                    "Доступные команды:\n"
                    "/start — приветствие\n"
                    "/help — подсказка\n"
                    "/feedback — отправить отзыв или предложение\n\n"
                    "Задания приходят в чат. Нажми кнопку «✅ Выполнил» на сообщении с заданием. "
                    "Если нужно — пришли фото или видео ответом на это сообщение."
                )
                schedule_message_delete(message.bot, message.chat.id, help_msg.message_id)
            else:
                help_msg = await message.answer(
                    "Доступные команды:\n"
                    "/start — регистрация\n"
                    "/help — список команд"
                )
                schedule_message_delete(message.bot, message.chat.id, help_msg.message_id)
        else:
            help_msg = await message.answer(
                "Доступные команды:\n"
                "/start — регистрация\n"
                "/feedback — отправить отзыв или предложение\n\n"
                "Обратитесь к администратору для добавления в систему."
            )
            schedule_message_delete(message.bot, message.chat.id, help_msg.message_id)


@router.message(Command("feedback"))
async def cmd_feedback(message: Message, state: FSMContext):
    """Команда /feedback — запрос текста обратной связи (доступна всем пользователям)."""
    await state.set_state(FeedbackStates.waiting_for_text)
    await message.answer("Напишите ваш отзыв или предложение одним сообщением.")


@router.message(F.text, FeedbackStates.waiting_for_text)
async def msg_feedback_text(message: Message, state: FSMContext):
    """Приём текста обратной связи и сохранение в БД."""
    text = message.text
    if not text or len(text.strip()) == 0:
        await message.answer("Пожалуйста, отправьте непустой текст.")
        return
    telegram_user_id = message.from_user.id if message.from_user else None
    user_id = None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        if user:
            user_id = user.id
        fb = Feedback(
            telegram_user_id=telegram_user_id,
            user_id=user_id,
            text=text.strip(),
        )
        session.add(fb)
        await session.commit()
    await state.clear()
    await message.answer("Спасибо, ваше сообщение сохранено.")

