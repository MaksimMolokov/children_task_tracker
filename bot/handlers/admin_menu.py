"""
Обработчики админ-меню через inline-кнопки.
См. SPEC.md раздел 7 "Админ-меню и кнопки бота"
"""
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from aiogram import F, Router
from sqlalchemy.orm import selectinload
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import ADMIN_TELEGRAM_ID, EVENT_LOG_FILE

# Названия дней недели на русском
WEEKDAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def get_week_days_string(week_start: date, week_end: date) -> str:
    """Получить строку с днями недели для периода"""
    days = []
    current = week_start
    while current <= week_end:
        weekday_name = WEEKDAYS_RU[current.weekday()]
        days.append(weekday_name)
        current += timedelta(days=1)
    return ", ".join(days)
from bot.keyboards.admin import (
    get_admin_children_menu,
    get_admin_check_tasks_menu,
    get_admin_leaders_menu,
    get_admin_main_menu,
    get_admin_reports_menu,
    get_admin_rewards_menu,
    get_back_button_menu,
    get_admin_reply_keyboard,
    ADMIN_BACK_MAIN,
    ADMIN_LOGS,
    REPLY_CHECK_TASKS,
    REPLY_ASSIGN_TASK,
    REPLY_CHILDREN,
    REPLY_REWARDS,
    REPLY_REPORTS,
    REPLY_ACCESS,
    REPLY_LEADERS,
    REPLY_TESTING,
    REPLY_LOGS,
)
from bot.middleware.auth import AdminMiddleware
from bot.utils.auto_delete import schedule_message_delete

# Задержка автоудаления сообщений отчётов и одноразовых ответов (сек)
REPORT_AUTO_DELETE_SEC = 45

router = Router()
router.callback_query.middleware(AdminMiddleware())
router.message.middleware(AdminMiddleware())

logger = logging.getLogger(__name__)


def format_admin_guide() -> str:
    """
    Форматирование гайда для администратора.
    Отражает текущий функционал: Доступы, дети через Доступы, Карточки, Расписания, Отчёты, Лидеры, Тестирование.
    """
    return (
        "📖 Гайд по работе с ботом\n\n"
        "Бот выдаёт детям задания по расписанию, принимает подтверждение выполнения (кнопка и медиа), "
        "считает выплаты по ставкам и отправляет ежедневные и еженедельные отчёты.\n\n"
        "1. Первый запуск — Доступы\n\n"
        "В разделе 🔐 Доступы добавьте администраторов и детей:\n"
        "– Имя, Telegram ID (узнать можно через @userinfobot), роль (Админ / Пользователь)\n"
        "– Для ребёнка укажите возраст. Дети добавляются только через Доступы.\n\n"
        "2. Как выдаются задания\n\n"
        "А) По расписанию: 🗓 Расписания → ➕ Новое расписание — выберите тип задания, время, дни недели и детей.\n"
        "Б) Вручную: ➕ Назначить задание — выберите ребёнка и карточку задания.\n\n"
        "3. Карточки заданий и ставки\n\n"
        "🗂 Карточки заданий: создание типов заданий (название, описание, время, награда, требуется ли медиа). "
        "Ставки по ребёнку настраиваются в том же разделе (по ребёнку или по типу задания).\n\n"
        "4. Проверка заданий\n\n"
        "📋 Проверка заданий: статус заданий на сегодня, по ребёнку, требующие проверки, просроченные. "
        "Дети нажимают «✅ Выполнил» на задании; если нужно медиа — отправляют фото/видео ответом на сообщение с заданием.\n\n"
        "5. Отчёты\n\n"
        "📊 Отчёты: за сегодня, вчера или неделю; Итого по всем детям или по каждому ребёнку. "
        "В отчёте указывается сумма выплаты за период.\n\n"
        "6. Лидеры и Тестирование\n\n"
        "🏆 Лидеры — просмотр по периоду. "
        "🧪 Тестирование — отправка тестового уведомления ребёнку для проверки доставки.\n\n"
        "7. Список команд\n\n"
        "/start — приветствие и вход в систему. Показывает меню (для админа) или инструкцию (для ребёнка).\n\n"
        "/admin — вход в админ-панель с выбором раздела (задания, дети, карточки, отчёты и т.д.).\n\n"
        "/help — краткий список доступных команд.\n\n"
        "Дополнительные команды (выполняются через меню):\n"
        "/add_child — подсказка, как добавить ребёнка (через Доступы).\n"
        "/add_task_type — подсказка по созданию карточки задания.\n"
        "/list_task_types — подсказка по просмотру карточек.\n"
        "/disable_task_type — подсказка по удалению карточки.\n"
        "/set_reward — подсказка по настройке ставок.\n"
        "/list_rewards — подсказка по списку ставок.\n"
        "/add_schedule — подсказка по добавлению расписания.\n"
        "/list_schedules — подсказка по списку расписаний.\n"
        "/disable_schedule — подсказка по отключению расписания."
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """
    Команда /admin - вход в админ-меню. Показываем постоянную клавиатуру внизу.
    """
    await message.answer(
        "🔧 Админ-панель\n\nВыберите действие (кнопки ниже):",
        reply_markup=get_admin_reply_keyboard(),
    )


# Обработчики нажатий нижней клавиатуры (ReplyKeyboard) — показываем подменю inline
@router.message(F.text == REPLY_CHECK_TASKS)
async def msg_check_tasks(message: Message):
    """Кнопка «Проверка заданий» — показываем подменю."""
    await message.answer(
        "📋 Проверка заданий\n\nВыберите действие:",
        reply_markup=get_admin_check_tasks_menu(),
    )


@router.message(F.text == REPLY_ASSIGN_TASK)
async def msg_assign_task(message: Message):
    """Кнопка «Назначить задание» — сообщение с одной inline-кнопкой для выбора карточки."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать карточку задания", callback_data="ADMIN_ASSIGN_TASK_LIST")],
    ])
    await message.answer("➕ Назначить задание\n\nВыберите карточку задания:", reply_markup=keyboard)


@router.message(F.text == REPLY_CHILDREN)
async def msg_children(message: Message):
    """Кнопка «Дети»."""
    await message.answer(
        "👦 Дети\n\n"
        "Просмотр списка детей.\n\n"
        "💡 Для добавления детей используйте раздел:\n"
        "🔐 Доступы → ➕ Добавить пользователя → выберите роль 'Пользователь'",
        reply_markup=get_admin_children_menu(),
    )


@router.message(F.text == REPLY_REWARDS)
async def msg_rewards(message: Message):
    """Кнопка «Карточки заданий»."""
    await message.answer(
        "🗂 Карточки заданий\n\nВыберите действие:",
        reply_markup=get_admin_rewards_menu(),
    )


@router.message(F.text == REPLY_REPORTS)
async def msg_reports(message: Message):
    """Кнопка «Отчёты»."""
    await message.answer(
        "📊 Отчёты\n\nВыберите период:",
        reply_markup=get_admin_reports_menu(),
    )


@router.message(F.text == REPLY_ACCESS)
async def msg_access(message: Message):
    """Кнопка «Доступы»."""
    from bot.keyboards.admin import get_admin_access_menu
    await message.answer(
        "🔐 Доступы\n\nВыберите действие:",
        reply_markup=get_admin_access_menu(),
    )


@router.message(F.text == REPLY_LEADERS)
async def msg_leaders(message: Message):
    """Кнопка «Лидеры»."""
    await message.answer(
        "🏆 Лидеры\n\nВыберите период:",
        reply_markup=get_admin_leaders_menu(),
    )


@router.message(F.text == REPLY_TESTING)
async def msg_testing(message: Message):
    """Кнопка «Тестирование» — сообщение с кнопкой, по нажатию показывается список детей."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать ребёнка для теста", callback_data="ADMIN_TESTING")],
    ])
    await message.answer(
        "🧪 Тестирование\n\nВыберите ребёнка для тестового уведомления:",
        reply_markup=keyboard,
    )


@router.message(F.text == REPLY_LOGS)
async def msg_logs(message: Message):
    """Кнопка «Логи» — отправляем последние записи журнала событий (две колонки)."""
    max_lines = 200
    max_chunk = 4000
    try:
        if not os.path.exists(EVENT_LOG_FILE):
            await message.answer("📜 Логи\n\nФайл событий пока не создан.")
            return
        with open(EVENT_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        last_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        text = _format_events_two_columns(last_lines)
        if len(text) > max_chunk:
            while text:
                chunk = text[:max_chunk]
                text = text[max_chunk:]
                await message.answer(chunk)
        else:
            await message.answer(text)
    except Exception as e:
        logger.exception("Ошибка при чтении логов")
        await message.answer(f"Ошибка при чтении логов: {e}")


@router.callback_query(lambda c: c.data == ADMIN_BACK_MAIN)
async def handle_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню (убираем inline, reply-клавиатура остаётся внизу)."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🔧 Админ-панель\n\nВыберите действие (кнопки ниже):",
        reply_markup=None,
    )


DATE_COLUMN_WIDTH = 19


def _format_events_two_columns(lines: list[str]) -> str:
    """Форматирует строки событий (дата\\tописание) в две колонки."""
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        date_part = (parts[0] if parts else "").ljust(DATE_COLUMN_WIDTH)
        desc = parts[1] if len(parts) > 1 else ""
        rows.append(f"{date_part} | {desc}")
    return "\n".join(rows) if rows else "Нет записей."


@router.callback_query(lambda c: c.data == ADMIN_LOGS)
async def handle_admin_logs(callback: CallbackQuery):
    """Отправка последних записей журнала событий админу (две колонки: дата | описание)."""
    await callback.answer()
    max_lines = 200
    max_chunk = 4000
    try:
        if not os.path.exists(EVENT_LOG_FILE):
            await callback.message.answer("📜 Логи\n\nФайл событий пока не создан.")
            return
        with open(EVENT_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        last_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        text = _format_events_two_columns(last_lines)
        if len(text) > max_chunk:
            while text:
                chunk = text[:max_chunk]
                text = text[max_chunk:]
                await callback.message.answer(chunk)
        else:
            await callback.message.answer(text)
    except Exception as e:
        logger.exception("Ошибка при чтении логов")
        await callback.message.answer(f"Ошибка при чтении логов: {e}")


@router.callback_query(lambda c: c.data == "ADMIN_CHECK_TASKS")
async def handle_check_tasks(callback: CallbackQuery):
    """
    Обработка "📋 Проверка заданий".
    См. SPEC.md раздел 7.2
    """
    await callback.answer()
    await callback.message.edit_text(
        "📋 Проверка заданий\n\n" "Выберите действие:",
        reply_markup=get_admin_check_tasks_menu(),
    )


@router.callback_query(lambda c: c.data == "ADMIN_CHECK_TODAY_BY_CHILD")
async def handle_check_today_by_child(callback: CallbackQuery):
    """
    Показ заданий на сегодня по всем детям.
    См. SPEC.md раздел 7.2.1
    """
    await callback.answer()
    from db.database import AsyncSessionLocal
    from db.models import Task, TaskStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        today = date.today()
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.child), selectinload(Task.task_type))
            .where(Task.scheduled_date == today)
        )
        tasks = result.scalars().all()

        if not tasks:
            text = f"📅 Задания на сегодня ({today})\n\n" "Нет заданий на сегодня."
        else:
            # Группировка по детям
            tasks_by_child = {}
            for task in tasks:
                child_name = task.child.display_name or f"Ребёнок {task.child_id}"
                if child_name not in tasks_by_child:
                    tasks_by_child[child_name] = []
                tasks_by_child[child_name].append(task)

            lines = [f"📅 Задания на сегодня ({today})\n"]
            for child_name, child_tasks in tasks_by_child.items():
                lines.append(f"👦 {child_name}")
                for task in child_tasks:
                    status_emoji = {
                        TaskStatus.DONE: "✅",
                        TaskStatus.FAILED: "❌",
                        TaskStatus.EXPIRED: "⏰",
                        TaskStatus.PENDING: "⏳",
                    }.get(task.status, "❓")
                    lines.append(f"– {task.task_type.name} — {status_emoji}")
                lines.append("")

            text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=get_admin_check_tasks_menu())


@router.callback_query(lambda c: c.data == "ADMIN_CHECK_BY_CHILD_SELECT")
async def handle_check_by_child_select(callback: CallbackQuery):
    """По ребёнку: показать список детей для выбора заданий на сегодня"""
    await callback.answer()
    from db.database import AsyncSessionLocal
    from db.models import User, UserRole
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = result.scalars().all()

    if not children:
        await callback.message.edit_text(
            "👦 По ребёнку\n\nНет активных детей.",
            reply_markup=get_admin_check_tasks_menu(),
        )
        return

    buttons = [
        [InlineKeyboardButton(text=f"👦 {c.display_name}", callback_data=f"ADMIN_CHECK_CHILD:{c.id}")]
        for c in children
    ]
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_CHECK_TASKS"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "👦 По ребёнку\n\nВыберите ребёнка, чтобы увидеть задания на сегодня:",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data.startswith("ADMIN_CHECK_CHILD:"))
async def handle_check_child_tasks(callback: CallbackQuery):
    """Задания на сегодня по выбранному ребёнку"""
    child_id = int(callback.data.split(":")[1])
    from db.database import AsyncSessionLocal
    from db.models import Task, TaskStatus, User, UserRole
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        child = await session.get(User, child_id)
        if not child or child.role != UserRole.CHILD:
            await callback.answer("Ребёнок не найден", show_alert=True)
            return
        await callback.answer()
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.task_type))
            .where(Task.scheduled_date == date.today(), Task.child_id == child_id)
        )
        tasks = result.scalars().all()

    child_name = child.display_name or f"Ребёнок {child_id}"
    if not tasks:
        text = f"📅 Задания на сегодня — {child_name}\n\nНет заданий на сегодня."
    else:
        lines = [f"📅 Задания на сегодня — {child_name}\n"]
        for task in tasks:
            status_emoji = {
                TaskStatus.DONE: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.EXPIRED: "⏰",
                TaskStatus.PENDING: "⏳",
            }.get(task.status, "❓")
            lines.append(f"– {task.task_type.name} — {status_emoji}")
        text = "\n".join(lines)

    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К списку детей", callback_data="ADMIN_CHECK_BY_CHILD_SELECT")],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_CHECK_TASKS"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
        ],
    ])
    await callback.message.edit_text(text, reply_markup=back_keyboard)


@router.callback_query(lambda c: c.data == "ADMIN_CHECK_NEED_REVIEW")
async def handle_check_need_review(callback: CallbackQuery):
    """Требуют проверки: задания на сегодня со статусом pending (ожидают подтверждения)"""
    await callback.answer()
    from db.database import AsyncSessionLocal
    from db.models import Task, TaskStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        today = date.today()
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.child), selectinload(Task.task_type), selectinload(Task.media))
            .where(Task.scheduled_date == today, Task.status == TaskStatus.PENDING)
        )
        tasks = result.scalars().all()

    if not tasks:
        text = "🔍 Требуют проверки\n\nНет заданий, ожидающих проверки на сегодня."
    else:
        lines = ["🔍 Требуют проверки (на сегодня)\n"]
        for task in tasks:
            child_name = task.child.display_name or f"Ребёнок {task.child_id}"
            media_note = " 📸" if task.media else ""
            lines.append(f"– {child_name}: {task.task_type.name}{media_note}")
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=get_admin_check_tasks_menu())


@router.callback_query(lambda c: c.data == "ADMIN_CHECK_FAILED_TODAY")
async def handle_check_failed_today(callback: CallbackQuery):
    """Просроченные / не сделаны: задания на сегодня со статусом failed, expired или pending"""
    await callback.answer()
    from db.database import AsyncSessionLocal
    from db.models import Task, TaskStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        today = date.today()
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.child), selectinload(Task.task_type))
            .where(
                Task.scheduled_date == today,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.FAILED, TaskStatus.EXPIRED]),
            )
        )
        tasks = result.scalars().all()

    if not tasks:
        text = "❌ Просроченные / не сделаны\n\nНет таких заданий на сегодня."
    else:
        tasks_by_child = {}
        for task in tasks:
            child_name = task.child.display_name or f"Ребёнок {task.child_id}"
            if child_name not in tasks_by_child:
                tasks_by_child[child_name] = []
            tasks_by_child[child_name].append(task)
        lines = ["❌ Просроченные / не сделаны (на сегодня)\n"]
        for child_name, child_tasks in tasks_by_child.items():
            lines.append(f"👦 {child_name}")
            for task in child_tasks:
                status_emoji = {
                    TaskStatus.PENDING: "⏳",
                    TaskStatus.FAILED: "❌",
                    TaskStatus.EXPIRED: "⏰",
                }.get(task.status, "❓")
                lines.append(f"– {task.task_type.name} — {status_emoji}")
            lines.append("")
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=get_admin_check_tasks_menu())


@router.callback_query(lambda c: c.data == "ADMIN_CHILDREN")
async def handle_children(callback: CallbackQuery):
    """
    Обработка "👦 Дети".
    См. SPEC.md раздел 7.5
    """
    await callback.answer()
    from bot.keyboards.admin import get_admin_children_menu
    await callback.message.edit_text(
        "👦 Дети\n\n"
        "Просмотр списка детей.\n\n"
        "💡 Для добавления детей используйте раздел:\n"
        "🔐 Доступы → ➕ Добавить пользователя → выберите роль 'Пользователь'",
        reply_markup=get_admin_children_menu(),
    )


@router.callback_query(lambda c: c.data == "ADMIN_REWARDS")
async def handle_rewards_menu(callback: CallbackQuery):
    """
    Обработка "🗂 Карточки заданий".
    Показывает меню с двумя кнопками: Список карточек и Создать новую.
    """
    await callback.answer()
    from bot.keyboards.admin import get_admin_rewards_menu
    await callback.message.edit_text(
        "🗂 Карточки заданий\n\n" "Выберите действие:",
        reply_markup=get_admin_rewards_menu(),
    )


@router.callback_query(lambda c: c.data == "ADMIN_ACCESS")
async def handle_access(callback: CallbackQuery):
    """
    Обработка "🔐 Доступы".
    Перенаправление в раздел управления доступами.
    """
    # Обработчик уже реализован в admin_access.py
    # Этот обработчик нужен для совместимости, но фактически обработка происходит в admin_access.router
    from bot.handlers.admin_access import handle_access_menu
    await handle_access_menu(callback)


@router.callback_query(lambda c: c.data == "ADMIN_REPORTS")
async def handle_reports(callback: CallbackQuery):
    """
    Обработка "📊 Отчёты".
    См. SPEC.md раздел 7.7
    """
    await callback.answer()
    await callback.message.edit_text(
        "📊 Отчёты\n\n" "Выберите период:",
        reply_markup=get_admin_reports_menu(),
    )


@router.callback_query(lambda c: c.data == "ADMIN_REPORT_PERIOD_TODAY")
async def handle_report_period_today(callback: CallbackQuery):
    """Выбран период 'сегодня' - показываем меню типа отчета"""
    await callback.answer()
    from bot.keyboards.admin import get_admin_report_type_menu
    await callback.message.edit_text(
        "📊 Отчёты\n\n" "Выберите тип отчета:",
        reply_markup=get_admin_report_type_menu("today"),
    )


@router.callback_query(lambda c: c.data == "ADMIN_REPORT_PERIOD_YESTERDAY")
async def handle_report_period_yesterday(callback: CallbackQuery):
    """Выбран период 'вчера' - показываем меню типа отчета"""
    await callback.answer()
    from bot.keyboards.admin import get_admin_report_type_menu
    await callback.message.edit_text(
        "📊 Отчёты\n\n" "Выберите тип отчета:",
        reply_markup=get_admin_report_type_menu("yesterday"),
    )


@router.callback_query(lambda c: c.data == "ADMIN_REPORT_PERIOD_WEEK")
async def handle_report_period_week(callback: CallbackQuery):
    """Выбран период 'за неделю' - показываем меню типа отчета"""
    await callback.answer()
    from bot.keyboards.admin import get_admin_report_type_menu
    await callback.message.edit_text(
        "📊 Отчёты\n\n" "Выберите тип отчета:",
        reply_markup=get_admin_report_type_menu("week"),
    )


@router.callback_query(lambda c: c.data.startswith("ADMIN_REPORT_TOTAL:"))
async def handle_report_total(callback: CallbackQuery):
    """Обработка выбора 'Итого' - отчет по всем детям"""
    period = callback.data.split(":")[1]  # "today", "yesterday", "week"
    
    from bot.services.report_service import ReportService
    from db.database import AsyncSessionLocal
    from datetime import date, timedelta
    
    async with AsyncSessionLocal() as session:
        if period == "today":
            report_date = date.today()
            report = await ReportService.generate_daily_report(session, report_date)
            
            # Проверка на пустой отчет
            if not report:
                msg = await callback.message.answer(
                    f"📊 Отчет за сегодня\n\n"
                    f"Нет данных за выбранный период."
                )
                schedule_message_delete(callback.bot, callback.message.chat.id, msg.message_id, REPORT_AUTO_DELETE_SEC)
                await callback.answer("Отчёт пуст")
                return
            
            # Отправляем отчет по каждому ребенку отдельным сообщением
            for child_id, child_data in report.items():
                child_report_text = (
                    f"📊 Отчет за сегодня\n\n"
                    f"👦 {child_data['child_name']}\n"
                    f"💰 Сумма выплаты: {child_data['total']} ARS\n\n"
                )
                
                for task_info in child_data["tasks"]:
                    status_emoji = "✅" if task_info["status"] == "done" else "❌"
                    media_icon = "📸" if task_info["has_media"] else ""
                    time_text = f" ({task_info['execution_time']} мин)" if task_info["execution_time"] > 0 and task_info["status"] == "done" else ""
                    child_report_text += (
                        f"– {task_info['task_type_name']} — {status_emoji} "
                        f"{task_info['reward_amount']} ARS{time_text} {media_icon}\n"
                    )
                
                total_time_text = f"{child_data['total_time']} минут" if child_data['total_time'] > 0 else "0 минут"
                child_report_text += (
                    f"\n⏱ Общее время выполнения: {total_time_text}\n"
                    f"💰 Сумма за выполненные задания: {child_data['total']} ARS"
                )
                sent = await callback.message.answer(child_report_text)
                schedule_message_delete(callback.bot, callback.message.chat.id, sent.message_id, REPORT_AUTO_DELETE_SEC)
            
            await callback.answer("Отчёты отправлены")
            
        elif period == "yesterday":
            report_date = date.today() - timedelta(days=1)
            report = await ReportService.generate_daily_report(session, report_date)
            
            # Проверка на пустой отчет
            if not report:
                msg = await callback.message.answer(
                    f"📊 Отчет за вчера ({report_date.strftime('%d.%m.%Y')})\n\n"
                    f"Нет данных за выбранный период."
                )
                schedule_message_delete(callback.bot, callback.message.chat.id, msg.message_id, REPORT_AUTO_DELETE_SEC)
                await callback.answer("Отчёт пуст")
                return
            
            # Отправляем отчет по каждому ребенку отдельным сообщением
            for child_id, child_data in report.items():
                child_report_text = (
                    f"📊 Отчет за вчера ({report_date.strftime('%d.%m.%Y')})\n\n"
                    f"👦 {child_data['child_name']}\n"
                    f"💰 Сумма выплаты: {child_data['total']} ARS\n\n"
                )
                
                for task_info in child_data["tasks"]:
                    status_emoji = "✅" if task_info["status"] == "done" else "❌"
                    media_icon = "📸" if task_info["has_media"] else ""
                    time_text = f" ({task_info['execution_time']} мин)" if task_info["execution_time"] > 0 and task_info["status"] == "done" else ""
                    child_report_text += (
                        f"– {task_info['task_type_name']} — {status_emoji} "
                        f"{task_info['reward_amount']} ARS{time_text} {media_icon}\n"
                    )
                
                total_time_text = f"{child_data['total_time']} минут" if child_data['total_time'] > 0 else "0 минут"
                child_report_text += (
                    f"\n⏱ Общее время выполнения: {total_time_text}\n"
                    f"💰 Сумма за выполненные задания: {child_data['total']} ARS"
                )
                sent = await callback.message.answer(child_report_text)
                schedule_message_delete(callback.bot, callback.message.chat.id, sent.message_id, REPORT_AUTO_DELETE_SEC)
            
            await callback.answer("Отчёты отправлены")
            
        elif period == "week":
            # За неделю - разбивка по дням, по каждому ребенку отдельное сообщение для каждого дня
            week_start = date.today() - timedelta(days=6)  # Последние 7 дней
            week_end = date.today()
            
            has_any_data = False
            
            # Получаем отчет за каждый день недели
            for day_offset in range(7):
                current_date = week_start + timedelta(days=day_offset)
                report = await ReportService.generate_daily_report(session, current_date)
                
                if report:  # Если есть данные за этот день
                    has_any_data = True
                    for child_id, child_data in report.items():
                        child_report_text = (
                            f"📊 Отчет за {current_date.strftime('%d.%m.%Y')}\n\n"
                            f"👦 {child_data['child_name']}\n"
                            f"💰 Сумма выплаты: {child_data['total']} ARS\n\n"
                        )
                        
                        for task_info in child_data["tasks"]:
                            status_emoji = "✅" if task_info["status"] == "done" else "❌"
                            media_icon = "📸" if task_info["has_media"] else ""
                            time_text = f" ({task_info['execution_time']} мин)" if task_info["execution_time"] > 0 and task_info["status"] == "done" else ""
                            child_report_text += (
                                f"– {task_info['task_type_name']} — {status_emoji} "
                                f"{task_info['reward_amount']} ARS{time_text} {media_icon}\n"
                            )
                        
                        total_time_text = f"{child_data['total_time']} минут" if child_data['total_time'] > 0 else "0 минут"
                        child_report_text += (
                            f"\n⏱ Общее время выполнения: {total_time_text}\n"
                            f"💰 Сумма за выполненные задания: {child_data['total']} ARS"
                        )
                        sent = await callback.message.answer(child_report_text)
                        schedule_message_delete(callback.bot, callback.message.chat.id, sent.message_id, REPORT_AUTO_DELETE_SEC)
            
            # Проверка на пустой отчет за всю неделю
            if not has_any_data:
                msg = await callback.message.answer(
                    f"📊 Отчет за неделю\n"
                    f"({week_start.strftime('%d.%m.%Y')} — {week_end.strftime('%d.%m.%Y')})\n\n"
                    f"Нет данных за выбранный период."
                )
                schedule_message_delete(callback.bot, callback.message.chat.id, msg.message_id, REPORT_AUTO_DELETE_SEC)
                await callback.answer("Отчёт пуст")
                return
            
            await callback.answer("Отчёты за неделю отправлены")


@router.callback_query(lambda c: c.data.startswith("ADMIN_REPORT_BY_CHILD:"))
async def handle_report_by_child(callback: CallbackQuery):
    """Обработка выбора 'По детям' - показываем список детей"""
    period = callback.data.split(":")[1]  # "today", "yesterday", "week"
    
    from db.database import AsyncSessionLocal
    from db.models import User, UserRole
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    async with AsyncSessionLocal() as session:
        # Получаем список активных детей
        result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = result.scalars().all()
        
        if not children:
            await callback.answer("Нет активных детей", show_alert=True)
            return
        
        buttons = []
        for child in children:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👦 {child.display_name}",
                    callback_data=f"ADMIN_REPORT_CHILD:{period}:{child.id}",
                )
            ])
        # Формируем правильный callback для возврата
        period_callbacks = {
            "today": "ADMIN_REPORT_PERIOD_TODAY",
            "yesterday": "ADMIN_REPORT_PERIOD_YESTERDAY",
            "week": "ADMIN_REPORT_PERIOD_WEEK"
        }
        back_callback = period_callbacks.get(period, "ADMIN_REPORTS")
        
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        period_text = {"today": "сегодня", "yesterday": "вчера", "week": "за неделю"}.get(period, period)
        
        await callback.message.edit_text(
            f"📊 Отчёты\n\n"
            f"Период: {period_text}\n\n"
            f"Выберите ребёнка:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_REPORT_CHILD:"))
async def handle_report_child_selected(callback: CallbackQuery):
    """Обработка выбора ребенка для отчета"""
    parts = callback.data.split(":")
    period = parts[1]  # "today", "yesterday", "week"
    child_id = int(parts[2])
    
    from bot.services.report_service import ReportService
    from db.database import AsyncSessionLocal
    from db.models import User, Task, TaskStatus
    from sqlalchemy import select
    from datetime import date, timedelta
    
    async with AsyncSessionLocal() as session:
        child = await session.get(User, child_id)
        if not child:
            await callback.answer("Ребёнок не найден", show_alert=True)
            return
        
        if period == "today":
            report_date = date.today()
            report = await ReportService.generate_daily_report(session, report_date)
            child_data = report.get(child_id)
            
            if not child_data:
                msg = await callback.message.answer(
                    f"📊 Отчет за сегодня\n\n"
                    f"👦 {child.display_name}\n\n"
                    f"Нет заданий за этот день."
                )
                schedule_message_delete(callback.bot, callback.message.chat.id, msg.message_id, REPORT_AUTO_DELETE_SEC)
            else:
                report_text = (
                    f"📊 Отчет за сегодня\n\n"
                    f"👦 {child_data['child_name']}\n"
                    f"💰 Сумма выплаты: {child_data['total']} ARS\n\n"
                )
                
                for task_info in child_data["tasks"]:
                    status_emoji = "✅" if task_info["status"] == "done" else "❌"
                    media_icon = "📸" if task_info["has_media"] else ""
                    time_text = f" ({task_info['execution_time']} мин)" if task_info["execution_time"] > 0 and task_info["status"] == "done" else ""
                    report_text += (
                        f"– {task_info['task_type_name']} — {status_emoji} "
                        f"{task_info['reward_amount']} ARS{time_text} {media_icon}\n"
                    )
                
                total_time_text = f"{child_data['total_time']} минут" if child_data['total_time'] > 0 else "0 минут"
                report_text += (
                    f"\n⏱ Общее время выполнения: {total_time_text}\n"
                    f"💰 Сумма за выполненные задания: {child_data['total']} ARS"
                )
                sent = await callback.message.answer(report_text)
                schedule_message_delete(callback.bot, callback.message.chat.id, sent.message_id, REPORT_AUTO_DELETE_SEC)
            
            await callback.answer("Отчёт отправлен")
            
        elif period == "yesterday":
            report_date = date.today() - timedelta(days=1)
            report = await ReportService.generate_daily_report(session, report_date)
            child_data = report.get(child_id)
            
            if not child_data:
                msg = await callback.message.answer(
                    f"📊 Отчет за вчера ({report_date.strftime('%d.%m.%Y')})\n\n"
                    f"👦 {child.display_name}\n\n"
                    f"Нет заданий за этот день."
                )
                schedule_message_delete(callback.bot, callback.message.chat.id, msg.message_id, REPORT_AUTO_DELETE_SEC)
            else:
                report_text = (
                    f"📊 Отчет за вчера ({report_date.strftime('%d.%m.%Y')})\n\n"
                    f"👦 {child_data['child_name']}\n"
                    f"💰 Сумма выплаты: {child_data['total']} ARS\n\n"
                )
                
                for task_info in child_data["tasks"]:
                    status_emoji = "✅" if task_info["status"] == "done" else "❌"
                    media_icon = "📸" if task_info["has_media"] else ""
                    time_text = f" ({task_info['execution_time']} мин)" if task_info["execution_time"] > 0 and task_info["status"] == "done" else ""
                    report_text += (
                        f"– {task_info['task_type_name']} — {status_emoji} "
                        f"{task_info['reward_amount']} ARS{time_text} {media_icon}\n"
                    )
                
                total_time_text = f"{child_data['total_time']} минут" if child_data['total_time'] > 0 else "0 минут"
                report_text += (
                    f"\n⏱ Общее время выполнения: {total_time_text}\n"
                    f"💰 Сумма за выполненные задания: {child_data['total']} ARS"
                )
                sent = await callback.message.answer(report_text)
                schedule_message_delete(callback.bot, callback.message.chat.id, sent.message_id, REPORT_AUTO_DELETE_SEC)
            
            await callback.answer("Отчёт отправлен")
            
        elif period == "week":
            # Отчет за неделю по конкретному ребенку
            week_start = date.today() - timedelta(days=6)
            week_end = date.today()
            
            # Получаем все задачи ребенка за неделю
            result = await session.execute(
                select(Task)
                .options(selectinload(Task.task_type))
                .where(
                    Task.child_id == child_id,
                    Task.scheduled_date >= week_start,
                    Task.scheduled_date <= week_end
                ).order_by(Task.scheduled_date)
            )
            tasks = result.scalars().all()
            
            if not tasks:
                msg = await callback.message.answer(
                    f"📊 Отчет за неделю\n\n"
                    f"👦 {child.display_name}\n\n"
                    f"Нет заданий за этот период."
                )
                schedule_message_delete(callback.bot, callback.message.chat.id, msg.message_id, REPORT_AUTO_DELETE_SEC)
            else:
                # Группируем по дням
                tasks_by_date = {}
                total_week = Decimal("0.00")
                total_time_week = 0
                
                from db.models import TaskMedia
                
                for task in tasks:
                    task_date = task.scheduled_date
                    if task_date not in tasks_by_date:
                        tasks_by_date[task_date] = []
                    tasks_by_date[task_date].append(task)
                    if task.status == TaskStatus.DONE:
                        total_week += task.reward_amount
                        total_time_week += task.task_type.execution_time or 0
                
                # Формируем отчет по дням
                # Первая строка - дата с которой по которую отчет
                # Вторая строка - дни недели
                # Третья строка - сумма выплаты за неделю
                week_days = get_week_days_string(week_start, week_end)
                report_text = (
                    f"📅 {week_start.strftime('%d.%m.%Y')} — {week_end.strftime('%d.%m.%Y')}\n"
                    f"{week_days}\n"
                    f"💰 Сумма выплаты за неделю: {total_week} ARS\n\n"
                    f"👦 {child.display_name}\n\n"
                )
                
                from db.models import TaskMedia
                
                for task_date in sorted(tasks_by_date.keys()):
                    day_tasks = tasks_by_date[task_date]
                    day_total = sum(t.reward_amount for t in day_tasks if t.status == TaskStatus.DONE)
                    day_total_time = sum(t.task_type.execution_time or 0 for t in day_tasks if t.status == TaskStatus.DONE)
                    
                    report_text += f"📅 {task_date.strftime('%d.%m.%Y')}\n"
                    report_text += f"💰 Сумма выплаты: {day_total} ARS\n\n"
                    for task in day_tasks:
                        status_emoji = "✅" if task.status == TaskStatus.DONE else "❌"
                        reward = task.reward_amount if task.status == TaskStatus.DONE else Decimal("0.00")
                        execution_time = task.task_type.execution_time or 0
                        time_text = f" ({execution_time} мин)" if execution_time > 0 and task.status == TaskStatus.DONE else ""
                        
                        # Проверяем наличие медиа
                        media_result = await session.execute(
                            select(TaskMedia).where(TaskMedia.task_id == task.id)
                        )
                        has_media = media_result.scalar_one_or_none() is not None
                        media_icon = "📸" if has_media else ""
                        
                        report_text += (
                            f"– {task.task_type.name} — {status_emoji} "
                            f"{reward} ARS{time_text} {media_icon}\n"
                        )
                    
                    day_time_text = f"{day_total_time} минут" if day_total_time > 0 else "0 минут"
                    report_text += (
                        f"⏱ Общее время за день: {day_time_text}\n"
                        f"💰 Итого за день: {day_total} ARS\n\n"
                    )
                
                total_time_text = f"{total_time_week} минут" if total_time_week > 0 else "0 минут"
                report_text += (
                    f"⏱ Общее время выполнения за неделю: {total_time_text}\n"
                )
                sent = await callback.message.answer(report_text)
                schedule_message_delete(callback.bot, callback.message.chat.id, sent.message_id, REPORT_AUTO_DELETE_SEC)
            
            await callback.answer("Отчёт отправлен")


@router.callback_query(lambda c: c.data == "ADMIN_LEADERS")
async def handle_leaders(callback: CallbackQuery):
    """
    Обработка "🏆 Лидеры".
    См. SPEC.md раздел 7.8
    """
    await callback.message.edit_text(
        "🏆 Лидеры\n\n" "Выберите период:",
        reply_markup=get_admin_leaders_menu(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_TESTING")
async def handle_testing(callback: CallbackQuery):
    """
    Обработка "🧪 Тестирование".
    """
    from bot.handlers.admin_testing import handle_testing_menu
    await handle_testing_menu(callback)


@router.callback_query(lambda c: c.data == "ADMIN_ASSIGN_TASK")
async def handle_assign_task(callback: CallbackQuery):
    """
    Обработка "➕ Назначить задание".
    Показывает список карточек заданий для выбора.
    """
    from bot.handlers.admin_task_types import handle_assign_task_list
    await handle_assign_task_list(callback)



@router.callback_query(lambda c: c.data == "ADMIN_ADD_TASK_TYPE")
async def handle_add_task_type_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик создания типа задания"""
    from bot.handlers.admin_rewards import handle_task_type_add_start
    await handle_task_type_add_start(callback, state)

@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_CHILD_SELECT")
async def handle_rewards_by_child_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора ребёнка для ставки"""
    from bot.handlers.admin_rewards import handle_rewards_by_child_select
    await handle_rewards_by_child_select(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD:"))
async def handle_reward_child_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора типа задания"""
    from bot.handlers.admin_rewards import handle_reward_child_selected
    await handle_reward_child_selected(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE:"))
async def handle_reward_task_type_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик ввода суммы"""
    from bot.handlers.admin_rewards import handle_reward_task_type_selected
    await handle_reward_task_type_selected(callback, state)

@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_TASKTYPE_SELECT")
async def handle_rewards_by_task_type_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора задания"""
    from bot.handlers.admin_rewards import handle_rewards_by_task_type_select
    await handle_rewards_by_task_type_select(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE_FIRST:"))
async def handle_reward_task_type_first_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора ребёнка после задания"""
    from bot.handlers.admin_rewards import handle_reward_task_type_first_selected
    await handle_reward_task_type_first_selected(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD_SECOND:"))
async def handle_reward_child_second_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик ввода суммы после выбора ребёнка вторым"""
    from bot.handlers.admin_rewards import handle_reward_child_second_selected
    await handle_reward_child_second_selected(callback, state)

# Обработчики для остальных пунктов меню (заглушки)
@router.callback_query(lambda c: c.data == "ADMIN_TASK_TYPE_LIST")
async def handle_task_type_list_redirect(callback: CallbackQuery):
    """Перенаправление на обработчик списка типов заданий"""
    from bot.handlers.admin_task_types import handle_task_type_list
    await handle_task_type_list(callback)

@router.callback_query(lambda c: c.data.startswith("ADMIN_TASK_TYPE_DELETE:"))
async def handle_task_type_delete_redirect(callback: CallbackQuery):
    """Перенаправление на обработчик удаления типа задания"""
    from bot.handlers.admin_task_types import handle_task_type_delete
    await handle_task_type_delete(callback)

@router.callback_query(lambda c: c.data.startswith("ADMIN_CHILD_DELETE:"))
async def handle_child_delete_redirect(callback: CallbackQuery):
    """Перенаправление на обработчик удаления ребёнка"""
    from bot.handlers.admin_children import handle_child_delete
    await handle_child_delete(callback)

@router.callback_query(lambda c: c.data.startswith("ADMIN_"))
async def handle_other_admin_callbacks(callback: CallbackQuery):
    """Заглушка для остальных админ-коллбеков"""
    # Игнорируем уже обработанные callback'и
    if callback.data in [
        "ADMIN_ADD_TASK_TYPE",
        "ADMIN_REWARD_CHILD:",
        "ADMIN_REWARD_TASK_TYPE:",
        "ADMIN_CHECK_BY_CHILD_SELECT",
        "ADMIN_CHECK_NEED_REVIEW",
        "ADMIN_CHECK_FAILED_TODAY",
    ] or callback.data.startswith((
        "ADMIN_REWARD_CHILD:",
        "ADMIN_REWARD_TASK_TYPE:",
        "ADMIN_TASK_TYPE_DELETE:",
        "ADMIN_CHILD_DELETE:",
        "ADMIN_CHILD_TASKS:",
        "ADMIN_USER_DELETE:",
        "ADMIN_USER_DELETE_CONFIRM:",
        "ADMIN_REWARD_TASK_TYPE_FIRST:",
        "ADMIN_REWARD_CHILD_SECOND:",
        "ADMIN_SCHEDULE",
        "ADMIN_CHECK_CHILD:",
    )):
        return
    await callback.answer("Функция в разработке", show_alert=True)

