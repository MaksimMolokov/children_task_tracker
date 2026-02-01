"""
Команды администратора.
См. SPEC.md раздел 4.2 "Управление типами заданий",
раздел 4.3 "Настройка денежной ставки",
раздел 4.4 "Настройка расписания"
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import ADMIN_TELEGRAM_ID
from bot.middleware.auth import AdminMiddleware

router = Router()

# Применяем middleware для проверки прав админа ко всем обработчикам
router.message.middleware(AdminMiddleware())


@router.message(Command("add_child"))
async def cmd_add_child(message: Message):
    """Команда /add_child — подсказка использовать меню"""
    await message.answer(
        "Добавление детей выполняется через меню. "
        "Используйте /admin → 🔐 Доступы → ➕ Добавить пользователя → выберите роль «Пользователь»."
    )


@router.message(Command("add_task_type"))
async def cmd_add_task_type(message: Message):
    """Команда /add_task_type — подсказка использовать меню"""
    await message.answer(
        "Создание карточек заданий — в меню. "
        "Используйте /admin → 🗂 Карточки заданий → ➕ Создать новую карточку."
    )


@router.message(Command("list_task_types"))
async def cmd_list_task_types(message: Message):
    """Команда /list_task_types — подсказка использовать меню"""
    await message.answer(
        "Список карточек заданий — в меню. "
        "Используйте /admin → 🗂 Карточки заданий → 📃 Список карточек."
    )


@router.message(Command("disable_task_type"))
async def cmd_disable_task_type(message: Message):
    """Команда /disable_task_type — подсказка использовать меню"""
    await message.answer(
        "Удаление карточки задания — в меню. "
        "Используйте /admin → 🗂 Карточки заданий → 📃 Список карточек → выберите карточку → удалить."
    )


@router.message(Command("set_reward"))
async def cmd_set_reward(message: Message):
    """Команда /set_reward — подсказка использовать меню"""
    await message.answer(
        "Настройка ставок — в меню. "
        "Используйте /admin → 🗂 Карточки заданий → 💰 Установить ставку (по ребёнку или по заданию)."
    )


@router.message(Command("list_rewards"))
async def cmd_list_rewards(message: Message):
    """Команда /list_rewards — подсказка использовать меню"""
    await message.answer(
        "Список ставок настраивается в меню. "
        "Используйте /admin → 🗂 Карточки заданий → 💰 Установить ставку."
    )


@router.message(Command("add_schedule"))
async def cmd_add_schedule(message: Message):
    """Команда /add_schedule — подсказка использовать меню"""
    await message.answer(
        "Добавление расписания — в меню. "
        "Используйте /admin → 🗓 Расписания → ➕ Новое расписание."
    )


@router.message(Command("list_schedules"))
async def cmd_list_schedules(message: Message):
    """Команда /list_schedules — подсказка использовать меню"""
    await message.answer(
        "Список расписаний — в меню. "
        "Используйте /admin → 🗓 Расписания → 📃 Список расписаний."
    )


@router.message(Command("disable_schedule"))
async def cmd_disable_schedule(message: Message):
    """Команда /disable_schedule — подсказка использовать меню"""
    await message.answer(
        "Управление расписаниями — в меню. "
        "Используйте /admin → 🗓 Расписания → 📃 Список расписаний → выберите расписание для отключения."
    )

