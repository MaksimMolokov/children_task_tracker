"""
Обработчики для управления ставками и типами заданий.
"""
import logging
from datetime import time

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.fsm_states import AddTaskTypeStates, SetRewardStates
from bot.keyboards.admin import get_admin_rewards_menu, get_back_button_menu
from bot.keyboards.callbacks import (
    REWARD_REPORT_YES,
    REWARD_REPORT_NO,
    REWARD_NOTIFY_YES,
    REWARD_NOTIFY_NO,
    REWARD_CONFIRM_CREATE,
    REWARD_RESTART,
)
from bot.utils.auto_delete import schedule_message_delete
from db.database import AsyncSessionLocal
from db.models import ChildTaskReward, Schedule, SchedulePeriodicity, TargetScope, TaskCategory, TaskType, User, UserRole
from decimal import Decimal

# Константы для дней недели
DAYS_OF_WEEK = {
    "MON": "Понедельник",
    "TUE": "Вторник",
    "WED": "Среда",
    "THU": "Четверг",
    "FRI": "Пятница",
    "SAT": "Суббота",
    "SUN": "Воскресенье",
}

WEEKDAYS = "MON,TUE,WED,THU,FRI"
WEEKENDS = "SAT,SUN"
ALL_DAYS = "MON,TUE,WED,THU,FRI,SAT,SUN"

router = Router()
logger = logging.getLogger(__name__)

from bot.middleware.auto_delete import AutoDeleteMiddleware

router.message.middleware(AutoDeleteMiddleware())


# ========== Обработчики для типов заданий ==========

@router.callback_query(lambda c: c.data == "ADMIN_ADD_TASK_TYPE")
async def handle_task_type_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало диалога добавления типа задания"""
    await callback.answer()
    await callback.message.edit_text(
        "➕ Создать новую карточку задания\n\n" "Введите название задания:",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_name)


@router.callback_query(StateFilter(AddTaskTypeStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_task_type_add_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления типа задания"""
    await callback.answer("Добавление отменено")
    await state.clear()
    from bot.keyboards.admin import get_admin_rewards_menu
    await callback.message.edit_text(
        "🗂 Карточки заданий\n\n" "Выберите действие:",
        reply_markup=get_admin_rewards_menu(),
    )

@router.callback_query(StateFilter(SetRewardStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_reward_set_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена установки ставки"""
    await callback.answer("Установка ставки отменена")
    await state.clear()
    from bot.keyboards.admin import get_admin_rewards_menu
    await callback.message.edit_text(
        "🗂 Карточки заданий\n\n" "Выберите действие:",
        reply_markup=get_admin_rewards_menu(),
    )

@router.message(AddTaskTypeStates.waiting_for_name)
async def handle_task_type_name(message: Message, state: FSMContext):
    """Обработка названия задания"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    name = message.text.strip()
    if not name or len(name) > 200:
        error_msg = await message.answer(
            "❌ Название должно быть от 1 до 200 символов. Попробуйте снова:",
            reply_markup=get_back_button_menu(),
        )
        schedule_message_delete(message.bot, message.chat.id, error_msg.message_id)
        return

    await state.update_data(task_type_name=name)
    await message.answer(
        f"✅ Название сохранено: {name}\n\n" "Введите описание задания (можно пропустить, отправив '-'):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_description)


@router.message(AddTaskTypeStates.waiting_for_description)
async def handle_task_type_description(message: Message, state: FSMContext):
    """Обработка описания задания"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    description = message.text.strip() if message.text.strip() != "-" else None

    await state.update_data(task_type_description=description)

    await message.answer(
        f"⏱ Введите время выполнения в минутах (число):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_execution_time)


# Удален хэндлер для выбора категории


@router.message(AddTaskTypeStates.waiting_for_execution_time)
async def handle_task_type_execution_time(message: Message, state: FSMContext):
    """Обработка времени выполнения"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        execution_time = int(message.text.strip())
        if execution_time < 1:
            raise ValueError("слишком маленькое значение")
        if execution_time > 480:  # 8 часов максимум
            raise ValueError("слишком большое значение")
    except ValueError as e:
        error_msg_text = "❌ Пожалуйста, введите число от 1 до 480 (минуты):"
        if "слишком маленькое" in str(e):
            error_msg_text = "❌ Время выполнения должно быть не менее 1 минуты:"
        elif "слишком большое" in str(e):
            error_msg_text = "❌ Время выполнения не может превышать 8 часов (480 минут):"

        error_msg = await message.answer(error_msg_text, reply_markup=get_back_button_menu())
        schedule_message_delete(message.bot, message.chat.id, error_msg.message_id)
        return

    await state.update_data(task_type_execution_time=execution_time)
    
    await message.answer(
        f"✅ Время выполнения сохранено: {execution_time} минут\n\n"
        f"💰 Введите стоимость выполнения задания (ARS):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_reward_amount)


@router.message(AddTaskTypeStates.waiting_for_reward_amount)
async def handle_task_type_reward_amount(message: Message, state: FSMContext):
    """Обработка ввода стоимости задания и переход к вопросу про отчет"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass

    try:
        amount = Decimal(message.text.strip())
        if amount < 0:
            raise ValueError("отрицательная сумма")
        if amount > 100000:  # Максимум 100k ARS
            raise ValueError("слишком большая сумма")
    except ValueError as e:
        error_msg_text = "❌ Пожалуйста, введите положительное число (сумма вознаграждения):"
        if "отрицательная" in str(e):
            error_msg_text = "❌ Сумма должна быть положительной:"
        elif "слишком большая" in str(e):
            error_msg_text = "❌ Сумма не может превышать 100,000 ARS:"

        error_msg = await message.answer(error_msg_text, reply_markup=get_back_button_menu())
        schedule_message_delete(message.bot, message.chat.id, error_msg.message_id)
        return

    # Сохраняем сумму в стейт
    await state.update_data(task_type_reward_amount=amount)

    # Спрашиваем про отчет кнопками
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [
            InlineKeyboardButton(text="📸 Да, нужен отчёт", callback_data=REWARD_REPORT_YES),
            InlineKeyboardButton(text="✅ Нет, отчёт не нужен", callback_data=REWARD_REPORT_NO),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена (в меню)", callback_data="ADMIN_REWARDS"),
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        f"✅ Стоимость сохранена: {amount} ARS\n\n"
        f"📸 Нужен ли отчёт по выполнению задания?",
        reply_markup=keyboard
    )
    await state.set_state(AddTaskTypeStates.waiting_for_report_choice)




@router.callback_query(lambda c: c.data in [REWARD_REPORT_YES, REWARD_REPORT_NO])
async def handle_report_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора необходимости отчета"""
    await callback.answer()
    requires_media = callback.data == REWARD_REPORT_YES
    await state.update_data(task_type_requires_media=requires_media)

    # Спрашиваем про уведомление при выполнении
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [
            InlineKeyboardButton(text="🔔 Да, уведомлять", callback_data=REWARD_NOTIFY_YES),
            InlineKeyboardButton(text="🔕 Нет", callback_data=REWARD_NOTIFY_NO),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена (в меню)", callback_data="ADMIN_REWARDS"),
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "🔔 Уведомлять вас при выполнении задания?\n\n"
        "При включении вы сразу получите сообщение, когда ребёнок выполнит это задание.",
        reply_markup=keyboard
    )
    await state.set_state(AddTaskTypeStates.waiting_for_notify_choice)


@router.callback_query(lambda c: c.data in [REWARD_NOTIFY_YES, REWARD_NOTIFY_NO])
async def handle_notify_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора уведомления при выполнении"""
    await callback.answer()
    notify_on_completion = callback.data == REWARD_NOTIFY_YES
    await state.update_data(task_type_notify_on_completion=notify_on_completion)

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [
            InlineKeyboardButton(text="📅 Каждый день", callback_data="TASK_SCHEDULE_PERIOD_DAILY"),
        ],
        [
            InlineKeyboardButton(text="🏢 Будни (Пн-Пт)", callback_data="TASK_SCHEDULE_PERIOD_WEEKDAYS"),
        ],
        [
            InlineKeyboardButton(text="🏖 Выходные (Сб-Вс)", callback_data="TASK_SCHEDULE_PERIOD_WEEKENDS"),
        ],
        [
            InlineKeyboardButton(text="📆 Раз в неделю (выбрать день)", callback_data="TASK_SCHEDULE_PERIOD_WEEKLY"),
        ],
        [
            InlineKeyboardButton(text="🗓 Выбрать конкретные дни", callback_data="TASK_SCHEDULE_PERIOD_CUSTOM"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Отмена (в меню)", callback_data="ADMIN_REWARDS"),
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "🗓 Создание расписания для карточки\n\n"
        "Выберите периодичность (когда бот будет напоминать о задании):",
        reply_markup=keyboard
    )
    await state.set_state(AddTaskTypeStates.waiting_for_schedule_periodicity)


# Обработчики создания расписания для карточки
@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_PERIOD_DAILY")
async def handle_task_schedule_period_daily(callback: CallbackQuery, state: FSMContext):
    """Выбрано ежедневно"""
    await callback.answer("✅ Периодичность: Каждый день")
    await state.update_data(
        schedule_days_of_week=ALL_DAYS,
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    await _show_task_schedule_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_PERIOD_WEEKDAYS")
async def handle_task_schedule_period_weekdays(callback: CallbackQuery, state: FSMContext):
    """Выбраны будни"""
    await callback.answer("✅ Периодичность: Будни (Пн-Пт)")
    await state.update_data(
        schedule_days_of_week=WEEKDAYS,
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    await _show_task_schedule_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_PERIOD_WEEKENDS")
async def handle_task_schedule_period_weekends(callback: CallbackQuery, state: FSMContext):
    """Выбраны выходные"""
    await callback.answer("✅ Периодичность: Выходные (Сб-Вс)")
    await state.update_data(
        schedule_days_of_week=WEEKENDS,
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    await _show_task_schedule_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_PERIOD_WEEKLY")
async def handle_task_schedule_period_weekly(callback: CallbackQuery, state: FSMContext):
    """Выбрано раз в неделю - выбираем день"""
    await callback.answer()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = []
    for day_code, day_name in DAYS_OF_WEEK.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"📅 {day_name}",
                callback_data=f"TASK_SCHEDULE_DAY:{day_code}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="TASK_SCHEDULE_PERIOD_BACK"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🗓 Создание расписания\n\n" "Выберите день недели:",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data.startswith("TASK_SCHEDULE_DAY:"))
async def handle_task_schedule_day_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран конкретный день недели"""
    await callback.answer(f"✅ День выбран: {DAYS_OF_WEEK.get(callback.data.split(':')[1], callback.data.split(':')[1])}")
    day_code = callback.data.split(":")[1]
    await state.update_data(
        schedule_days_of_week=day_code,
        schedule_periodicity=SchedulePeriodicity.WEEKLY,
    )
    await _show_task_schedule_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_PERIOD_CUSTOM")
async def handle_task_schedule_period_custom(callback: CallbackQuery, state: FSMContext, skip_answer: bool = False):
    """Выбор пользовательских дней"""
    if not skip_answer:
        await callback.answer()
    data = await state.get_data()
    selected_days = data.get("schedule_selected_days", [])

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = []
    for day_code, day_name in DAYS_OF_WEEK.items():
        is_selected = day_code in selected_days
        prefix = "✅" if is_selected else "⬜"
        buttons.append([
            InlineKeyboardButton(
                text=f"{prefix} {day_name}",
                callback_data=f"TASK_SCHEDULE_TOGGLE_DAY:{day_code}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ Готово",
            callback_data="TASK_SCHEDULE_DAYS_DONE",
        )
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="TASK_SCHEDULE_PERIOD_BACK"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    selected_text = f"Выбрано: {len(selected_days)}" if selected_days else "Выберите дни:"

    await callback.message.edit_text(
        f"🗓 Создание расписания\n\n{selected_text}\n\n" "Нажмите на день для выбора/снятия выбора:",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data.startswith("TASK_SCHEDULE_TOGGLE_DAY:"))
async def handle_task_schedule_toggle_day(callback: CallbackQuery, state: FSMContext):
    """Переключение выбора дня"""
    day_code = callback.data.split(":")[1]
    data = await state.get_data()
    selected_days = data.get("schedule_selected_days", [])

    day_name = DAYS_OF_WEEK.get(day_code, day_code)
    
    if day_code in selected_days:
        selected_days.remove(day_code)
        await callback.answer(f"❌ {day_name} убран из выбора")
    else:
        selected_days.append(day_code)
        await callback.answer(f"✅ {day_name} добавлен")
    
    await state.update_data(schedule_selected_days=selected_days)
    
    # Возвращаемся к выбору дней (уже ответили выше — не вызывать answer повторно)
    await handle_task_schedule_period_custom(callback, state, skip_answer=True)


@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_DAYS_DONE")
async def handle_task_schedule_days_done(callback: CallbackQuery, state: FSMContext):
    """Дни выбраны, переходим к выбору времени"""
    data = await state.get_data()
    selected_days = data.get("schedule_selected_days", [])

    if not selected_days:
        await callback.answer("❌ Выберите хотя бы один день", show_alert=True)
        return

    days_names = ", ".join([DAYS_OF_WEEK.get(day, day) for day in selected_days])
    await callback.answer(f"✅ Дни выбраны: {days_names}")
    await state.update_data(
        schedule_days_of_week=",".join(selected_days),
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    await _show_task_schedule_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_PERIOD_BACK")
async def handle_task_schedule_period_back(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору периодичности"""
    await callback.answer()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    buttons = [
        [
            InlineKeyboardButton(text="📅 Каждый день", callback_data="TASK_SCHEDULE_PERIOD_DAILY"),
        ],
        [
            InlineKeyboardButton(text="🏢 Будни (Пн-Пт)", callback_data="TASK_SCHEDULE_PERIOD_WEEKDAYS"),
        ],
        [
            InlineKeyboardButton(text="🏖 Выходные (Сб-Вс)", callback_data="TASK_SCHEDULE_PERIOD_WEEKENDS"),
        ],
        [
            InlineKeyboardButton(text="📆 Раз в неделю (выбрать день)", callback_data="TASK_SCHEDULE_PERIOD_WEEKLY"),
        ],
        [
            InlineKeyboardButton(text="🗓 Выбрать конкретные дни", callback_data="TASK_SCHEDULE_PERIOD_CUSTOM"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Отмена (в меню)", callback_data="ADMIN_REWARDS"),
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🗓 Создание расписания для карточки\n\n"
        "Выберите периодичность (когда бот будет напоминать о задании):",
        reply_markup=keyboard
    )
    await state.set_state(AddTaskTypeStates.waiting_for_schedule_periodicity)


async def _show_task_schedule_time_selection(callback: CallbackQuery, state: FSMContext):
    """Показ выбора времени для расписания карточки"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    # Предопределённые времена
    times = ["08:00", "09:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
    
    buttons = []
    row = []
    for i, time_str in enumerate(times):
        row.append(
            InlineKeyboardButton(
                text=f"🕐 {time_str}",
                callback_data=f"TASK_SCHEDULE_TIME:{time_str}",
            )
        )
        if len(row) == 2 or i == len(times) - 1:
            buttons.append(row)
            row = []

    buttons.append([
        InlineKeyboardButton(
            text="✏️ Ввести своё время",
            callback_data="TASK_SCHEDULE_TIME_CUSTOM",
        )
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="TASK_SCHEDULE_PERIOD_BACK"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.answer()
    await callback.message.edit_text(
        "🗓 Создание расписания\n\n" "Выберите время отправки:",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data.startswith("TASK_SCHEDULE_TIME:"))
async def handle_task_schedule_time_selected(callback: CallbackQuery, state: FSMContext):
    """Время выбрано из предопределённых"""
    await callback.answer(f"✅ Время выбрано: {callback.data.replace('TASK_SCHEDULE_TIME:', '')}")
    time_str = callback.data.replace("TASK_SCHEDULE_TIME:", "")
    hours, minutes = map(int, time_str.split(":"))
    schedule_time = time(hours, minutes)
    await state.update_data(schedule_time=schedule_time)
    await _show_task_card_summary(callback, state)


@router.callback_query(lambda c: c.data == "TASK_SCHEDULE_TIME_CUSTOM")
async def handle_task_schedule_time_custom(callback: CallbackQuery, state: FSMContext):
    """Запрос ввода времени"""
    await callback.answer()
    await callback.message.edit_text(
        "🗓 Создание расписания\n\n"
        "Введите время в формате HH:MM (например, 09:30):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_schedule_time)


@router.message(AddTaskTypeStates.waiting_for_schedule_time)
async def handle_task_schedule_time_input(message: Message, state: FSMContext):
    """Обработка введённого времени"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass

    try:
        time_str = message.text.strip()
        hours, minutes = map(int, time_str.split(":"))
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
        schedule_time = time(hours, minutes)
    except (ValueError, Exception):
        error_msg = await message.answer(
            "❌ Неверный формат времени. Используйте формат HH:MM (например, 09:30):",
            reply_markup=get_back_button_menu(),
        )
        schedule_message_delete(message.bot, message.chat.id, error_msg.message_id)
        return

    await state.update_data(schedule_time=schedule_time)
    
    # Показываем summary карточки
    await _show_task_card_summary(message, state)


async def _show_task_card_summary(message_or_callback, state: FSMContext):
    """Показ полного summary карточки с расписанием"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    data = await state.get_data()
    requires_media = data.get("task_type_requires_media", False)
    
    # Формируем информацию о расписании
    periodicity = data.get("schedule_periodicity")
    days_of_week = data.get("schedule_days_of_week", "")
    schedule_time = data.get("schedule_time")
    
    if periodicity == SchedulePeriodicity.DAILY:
        if days_of_week == ALL_DAYS:
            schedule_text = "Каждый день"
        elif days_of_week == WEEKDAYS:
            schedule_text = "Будни (Пн-Пт)"
        elif days_of_week == WEEKENDS:
            schedule_text = "Выходные (Сб-Вс)"
        else:
            # Пользовательские дни
            days_list = days_of_week.split(",")
            days_names = [DAYS_OF_WEEK.get(day, day) for day in days_list]
            schedule_text = ", ".join(days_names)
    elif periodicity == SchedulePeriodicity.WEEKLY:
        day_name = DAYS_OF_WEEK.get(days_of_week, days_of_week)
        schedule_text = f"Раз в неделю ({day_name})"
    else:
        schedule_text = "Не указано"
    
    time_str = schedule_time.strftime("%H:%M") if schedule_time else "не указано"
    
    notify_on_completion = data.get("task_type_notify_on_completion", False)
    summary_text = (
        f"📝 Проверка данных карточки задания\n\n"
        f"📋 Название: {data['task_type_name']}\n"
        f"📝 Описание: {data.get('task_type_description') or 'не указано'}\n"
        f"⏱ Время выполнения: {data.get('task_type_execution_time')} минут\n"
        f"💰 Стоимость: {data.get('task_type_reward_amount')} ARS\n"
        f"📸 Отчёт: {'требуется' if requires_media else 'не требуется'}\n"
        f"🔔 Уведомление при выполнении: {'да' if notify_on_completion else 'нет'}\n"
        f"🗓 Расписание: {schedule_text}\n"
        f"🕐 Время отправки: {time_str}\n\n"
        f"Подтверждаете создание карточки?"
    )

    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, создать карточку", callback_data=REWARD_CONFIRM_CREATE),
        ],
        [
            InlineKeyboardButton(text="❌ Нет, начать заново", callback_data=REWARD_RESTART),
        ],
        [
            InlineKeyboardButton(text="⬅️ Отмена (в меню)", callback_data="ADMIN_REWARDS"),
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(summary_text, reply_markup=keyboard)
    else:
        await message_or_callback.message.edit_text(summary_text, reply_markup=keyboard)
    
    await state.set_state(AddTaskTypeStates.waiting_for_confirmation)


@router.callback_query(lambda c: c.data == REWARD_CONFIRM_CREATE)
async def handle_confirm_create_task(callback: CallbackQuery, state: FSMContext):
    """Финальное создание карточки задания"""
    await callback.answer()
    data = await state.get_data()
    requires_media = data.get("task_type_requires_media", False)
    notify_on_completion = data.get("task_type_notify_on_completion", False)

    # Сохранение типа задания в БД
    async with AsyncSessionLocal() as session:
        category = data.get("task_type_category", TaskCategory.OTHER)

        task_type = TaskType(
            name=data["task_type_name"],
            description=data.get("task_type_description"),
            category=category,
            execution_time=data.get("task_type_execution_time"),
            reward_amount=data.get("task_type_reward_amount", Decimal("0.00")),
            requires_media=requires_media,
            notify_on_completion=notify_on_completion,
            is_active=True,
        )
        session.add(task_type)
        await session.commit()
        await session.refresh(task_type)

        # Сохранение расписания в БД
        schedule_periodicity = data.get("schedule_periodicity")
        schedule_days_of_week = data.get("schedule_days_of_week", "")
        schedule_time = data.get("schedule_time")
        
        if schedule_periodicity and schedule_days_of_week and schedule_time:
            schedule = Schedule(
                task_type_id=task_type.id,
                periodicity=schedule_periodicity,
                time_of_day=schedule_time,
                days_of_week=schedule_days_of_week,
                target_scope=TargetScope.ALL_CHILDREN,  # По умолчанию для всех детей
                target_children_ids=None,
                is_active=True,
            )
            session.add(schedule)
            await session.commit()

    # Показываем успешное сообщение
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [
            InlineKeyboardButton(
                text="📋 К списку заданий",
                callback_data="ADMIN_TASK_TYPE_LIST",
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ В меню", callback_data="ADMIN_REWARDS")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    result_text = (
        f"✅ Карточка задания успешно создана!\n\n"
        f"📋 {task_type.name}\n"
        f"📝 {task_type.description}\n"
        f"⏱ {task_type.execution_time} минут\n"
        f"💰 Стоимость: {data['task_type_reward_amount']} ARS\n"
        f"📸 Отчёт: {'требуется' if requires_media else 'не требуется'}\n"
        f"🔔 Уведомление при выполнении: {'да' if notify_on_completion else 'нет'}\n"
        f"🆔 ID: {task_type.id}"
    )

    await callback.message.edit_text(result_text, reply_markup=keyboard)
    schedule_message_delete(callback.bot, callback.message.chat.id, callback.message.message_id)
    await state.clear()


@router.callback_query(lambda c: c.data == REWARD_RESTART)
async def handle_restart_task_creation(callback: CallbackQuery, state: FSMContext):
    """Перезапуск создания карточки задания"""
    await callback.answer("Создание карточки начато заново")
    await state.clear()
    await callback.message.edit_text(
        "➕ Создать новую карточку задания\n\n" "Введите название задания:",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_name)






# ========== Обработчики для ставок ==========

@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_CHILD_SELECT")
async def handle_rewards_by_child_select(callback: CallbackQuery, state: FSMContext):
    """Выбор ребёнка для установки ставки"""
    await callback.answer()
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = result.scalars().all()

        if not children:
            await callback.message.edit_text(
                "❌ Нет активных детей. Сначала добавьте ребёнка.",
                reply_markup=get_admin_rewards_menu(),
            )
            return

        # Формируем список детей кнопками
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        buttons = []
        for child in children:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👦 {child.display_name} ({child.age} лет)" if child.age else f"👦 {child.display_name}",
                    callback_data=f"ADMIN_REWARD_CHILD:{child.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            "🗂 Установка ставки по ребёнку\n\n" "Выберите ребёнка:",
            reply_markup=keyboard,
        )


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD:"))
async def handle_reward_child_selected(callback: CallbackQuery, state: FSMContext):
    """Ребёнок выбран, теперь выбираем тип задания"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(reward_child_id=child_id)

    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one_or_none()
        if not child:
            await callback.answer("Ребёнок не найден", show_alert=True)
            return
        await callback.answer(f"✅ Выбран ребёнок: {child.display_name}")

        task_types_result = await session.execute(
            select(TaskType).where(TaskType.is_active == True)
        )
        task_types = task_types_result.scalars().all()

        if not task_types:
            await callback.message.edit_text(
                "❌ Нет активных типов заданий. Сначала создайте тип задания.",
                reply_markup=get_admin_rewards_menu(),
            )
            return

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = []
        for task_type in task_types:
            buttons.append([
                InlineKeyboardButton(
                    text=f"📋 {task_type.name}",
                    callback_data=f"ADMIN_REWARD_TASK_TYPE:{task_type.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(
            f"🗂 Установка ставки для {child.display_name}\n\n" "Выберите тип задания:",
            reply_markup=keyboard,
        )


@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_TASKTYPE_SELECT")
async def handle_rewards_by_task_type_select(callback: CallbackQuery, state: FSMContext):
    """Выбор типа задания для установки ставки"""
    await callback.answer()
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        task_types_result = await session.execute(
            select(TaskType).where(TaskType.is_active == True)
        )
        task_types = task_types_result.scalars().all()

        if not task_types:
            await callback.message.edit_text(
                "❌ Нет активных типов заданий. Сначала создайте тип задания.",
                reply_markup=get_admin_rewards_menu(),
            )
            return

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = []
        for task_type in task_types:
            buttons.append([
                InlineKeyboardButton(
                    text=f"📋 {task_type.name}",
                    callback_data=f"ADMIN_REWARD_TASK_TYPE_FIRST:{task_type.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(
            "🗂 Установка ставки по заданию\n\n" "Выберите тип задания:",
            reply_markup=keyboard,
        )


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE_FIRST:"))
async def handle_reward_task_type_first_selected(callback: CallbackQuery, state: FSMContext):
    """Тип задания выбран первым, теперь выбираем ребёнка"""
    task_type_id = int(callback.data.split(":")[1])
    await state.update_data(reward_task_type_id=task_type_id)

    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one_or_none()
        if not task_type:
            await callback.answer("Тип задания не найден", show_alert=True)
            return
        await callback.answer(f"✅ Выбрано задание: {task_type.name}")

        children_result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = children_result.scalars().all()

        if not children:
            await callback.message.edit_text(
                "❌ Нет активных детей. Сначала добавьте ребёнка.",
                reply_markup=get_admin_rewards_menu(),
            )
            return

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = []
        for child in children:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👦 {child.display_name} ({child.age} лет)" if child.age else f"👦 {child.display_name}",
                    callback_data=f"ADMIN_REWARD_CHILD_SECOND:{child.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад в меню ставок", callback_data="ADMIN_REWARDS"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(
            f"🗂 Установка ставки для {task_type.name}\n\n" "Выберите ребёнка:",
            reply_markup=keyboard,
        )


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD_SECOND:"))
async def handle_reward_child_second_selected(callback: CallbackQuery, state: FSMContext):
    """Ребёнок выбран вторым, запрашиваем сумму"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(reward_child_id=child_id)

    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()
    await callback.answer(f"✅ Выбран ребёнок: {child.display_name}")
    await callback.message.edit_text(
        "💰 Установка ставки\n\n"
        "Введите сумму вознаграждения (число, например: 1000):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(SetRewardStates.waiting_for_amount)


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE:"))
async def handle_reward_task_type_selected(callback: CallbackQuery, state: FSMContext):
    """Тип задания выбран, запрашиваем сумму"""
    task_type_id = int(callback.data.split(":")[1])
    await state.update_data(reward_task_type_id=task_type_id)

    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one()
    await callback.answer(f"✅ Выбрано задание: {task_type.name}")
    await callback.message.edit_text(
        "💰 Установка ставки\n\n"
        "Введите сумму вознаграждения (число, например: 1000):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(SetRewardStates.waiting_for_amount)


@router.message(SetRewardStates.waiting_for_amount)
async def handle_reward_amount(message: Message, state: FSMContext):
    """Обработка суммы ставки"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        amount = Decimal(message.text.strip())
        if amount < 0:
            error_msg = await message.answer(
                "❌ Сумма должна быть положительной. Попробуйте снова:",
                reply_markup=get_back_button_menu(),
            )
            schedule_message_delete(message.bot, message.chat.id, error_msg.message_id)
            return
    except (ValueError, Exception):
        error_msg = await message.answer(
            "❌ Пожалуйста, введите число (сумма вознаграждения):",
            reply_markup=get_back_button_menu(),
        )
        schedule_message_delete(message.bot, message.chat.id, error_msg.message_id)
        return

    data = await state.get_data()
    child_id = data.get("reward_child_id")
    task_type_id = data.get("reward_task_type_id")

    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Проверяем существующую ставку
        existing_result = await session.execute(
            select(ChildTaskReward).where(
                ChildTaskReward.child_id == child_id,
                ChildTaskReward.task_type_id == task_type_id,
            )
        )
        existing_reward = existing_result.scalar_one_or_none()

        # Получаем имена для отображения
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()

        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one()

        if existing_reward:
            # Обновляем существующую ставку
            existing_reward.reward_amount = amount
            await session.commit()
            status_text = "обновлена"
        else:
            # Создаём новую ставку
            reward = ChildTaskReward(
                child_id=child_id,
                task_type_id=task_type_id,
                reward_amount=amount,
                currency="ARS",
            )
            session.add(reward)
            await session.commit()
            status_text = "установлена"

    await message.answer(
        f"✅ Ставка {status_text}!\n\n"
        f"👦 Ребёнок: {child.display_name}\n"
        f"📋 Задание: {task_type.name}\n"
        f"💰 Сумма: {amount} ARS",
        reply_markup=get_admin_rewards_menu(),
    )
    await state.clear()

