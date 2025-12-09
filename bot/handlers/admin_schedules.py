"""
Обработчики для управления расписаниями.
"""
import asyncio
import logging
from datetime import time

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.fsm_states import AddScheduleStates
from bot.keyboards.admin import get_admin_schedules_menu, get_back_button_menu
from bot.middleware.auth import AdminMiddleware
from db.database import AsyncSessionLocal
from db.models import ChildTaskReward, Schedule, SchedulePeriodicity, TargetScope, TaskType, User, UserRole

router = Router()
logger = logging.getLogger(__name__)

router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
from bot.middleware.auto_delete import AutoDeleteMiddleware
router.message.middleware(AutoDeleteMiddleware())

# Mapping дней недели
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


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_ADD")
async def handle_schedule_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало диалога добавления расписания - сначала выбираем ребёнка"""
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        # Получаем детей
        children_result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = children_result.scalars().all()

        if not children:
            await callback.message.edit_text(
                "❌ Нет активных детей. Сначала добавьте ребёнка.",
                reply_markup=get_admin_schedules_menu(),
            )
            await callback.answer()
            return

        # Формируем список детей кнопками
        buttons = []
        for child in children:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👦 {child.display_name} ({child.age} лет)" if child.age else f"👦 {child.display_name}",
                    callback_data=f"ADMIN_SCHEDULE_CHILD:{child.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_SCHEDULES")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            "🗓 **Новое расписание**\n\n"
            "Выберите ребёнка, для которого создаётся расписание.\n"
            "Бот будет отправлять напоминания о заданиях в личные сообщения этому ребёнку:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_SCHEDULE_CHILD:"))
async def handle_schedule_child_selected(callback: CallbackQuery, state: FSMContext):
    """Ребёнок выбран, теперь выбираем задание"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(schedule_child_id=child_id)
    await callback.answer("✅ Ребёнок выбран")

    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        # Получаем имя ребёнка для отображения
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()

        # Получаем типы заданий
        task_types_result = await session.execute(
            select(TaskType).where(TaskType.is_active == True)
        )
        task_types = task_types_result.scalars().all()

        if not task_types:
            await callback.message.edit_text(
                "❌ Нет активных типов заданий. Сначала создайте тип задания в меню 'Ставки'.",
                reply_markup=get_admin_schedules_menu(),
            )
            await callback.answer()
            return

        # Формируем список заданий кнопками
        buttons = []
        for task_type in task_types:
            buttons.append([
                InlineKeyboardButton(
                    text=f"📋 {task_type.name}",
                    callback_data=f"ADMIN_SCHEDULE_TASK_TYPE:{task_type.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_SCHEDULE_ADD")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"🗓 **Новое расписание для {child.display_name}**\n\n"
            "Выберите задание из перечня:\n"
            "(Бот будет напоминать об этом задании в указанное время)",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_SCHEDULE_TASK_TYPE:"))
async def handle_schedule_task_type_selected(callback: CallbackQuery, state: FSMContext):
    """Задание выбрано, переходим к выбору периодичности"""
    task_type_id = int(callback.data.split(":")[1])
    await state.update_data(schedule_task_type_id=task_type_id)
    
    # Получаем название задания для подтверждения
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one()
    await callback.answer(f"✅ Задание выбрано: {task_type.name}")

    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        # Получаем информацию для отображения
        child_result = await session.execute(
            select(User).where(User.id == (await state.get_data()).get("schedule_child_id"))
        )
        child = child_result.scalar_one()

        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one()

    buttons = [
        [
            InlineKeyboardButton(
                text="📅 Каждый день",
                callback_data="ADMIN_SCHEDULE_PERIOD_DAILY",
            )
        ],
        [
            InlineKeyboardButton(
                text="🏢 Будни (Пн-Пт)",
                callback_data="ADMIN_SCHEDULE_PERIOD_WEEKDAYS",
            )
        ],
        [
            InlineKeyboardButton(
                text="🏖 Выходные (Сб-Вс)",
                callback_data="ADMIN_SCHEDULE_PERIOD_WEEKENDS",
            )
        ],
        [
            InlineKeyboardButton(
                text="📆 Раз в неделю (выбрать день)",
                callback_data="ADMIN_SCHEDULE_PERIOD_WEEKLY",
            )
        ],
        [
            InlineKeyboardButton(
                text="🗓 Выбрать конкретные дни",
                callback_data="ADMIN_SCHEDULE_PERIOD_CUSTOM",
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ADMIN_SCHEDULE_CHILD:{child.id}")
        ],
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        f"🗓 **Новое расписание**\n\n"
        f"👦 Ребёнок: {child.display_name}\n"
        f"📋 Задание: {task_type.name}\n\n"
        f"Выберите периодичность (когда бот будет напоминать):",
        reply_markup=keyboard,
    )
    await callback.answer()




# Обработчики периодичности
@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_PERIOD_DAILY")
async def handle_schedule_period_daily(callback: CallbackQuery, state: FSMContext):
    """Выбрано ежедневно"""
    await state.update_data(
        schedule_days_of_week=ALL_DAYS,
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    await callback.answer("✅ Периодичность: Каждый день")
    await _show_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_PERIOD_WEEKDAYS")
async def handle_schedule_period_weekdays(callback: CallbackQuery, state: FSMContext):
    """Выбраны будни"""
    await state.update_data(
        schedule_days_of_week=WEEKDAYS,
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    await callback.answer("✅ Периодичность: Будни (Пн-Пт)")
    await _show_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_PERIOD_WEEKENDS")
async def handle_schedule_period_weekends(callback: CallbackQuery, state: FSMContext):
    """Выбраны выходные"""
    await state.update_data(
        schedule_days_of_week=WEEKENDS,
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    await callback.answer("✅ Периодичность: Выходные (Сб-Вс)")
    await _show_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_PERIOD_WEEKLY")
async def handle_schedule_period_weekly(callback: CallbackQuery, state: FSMContext):
    """Выбрано раз в неделю - выбираем день"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = []
    for day_code, day_name in DAYS_OF_WEEK.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"📅 {day_name}",
                callback_data=f"ADMIN_SCHEDULE_DAY:{day_code}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_SCHEDULE_PERIOD_BACK")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🗓 **Новое расписание**\n\n" "Выберите день недели:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_SCHEDULE_DAY:"))
async def handle_schedule_day_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран конкретный день недели"""
    day_code = callback.data.split(":")[1]
    day_name = DAYS_OF_WEEK.get(day_code, day_code)
    await state.update_data(
        schedule_days_of_week=day_code,
        schedule_periodicity=SchedulePeriodicity.WEEKLY,
    )
    await callback.answer(f"✅ День выбран: {day_name}")
    await _show_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_PERIOD_CUSTOM")
async def handle_schedule_period_custom(callback: CallbackQuery, state: FSMContext):
    """Выбор пользовательских дней"""
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
                callback_data=f"ADMIN_SCHEDULE_TOGGLE_DAY:{day_code}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ Готово",
            callback_data="ADMIN_SCHEDULE_DAYS_DONE",
        )
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_SCHEDULE_PERIOD_BACK")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    selected_text = f"Выбрано: {len(selected_days)}" if selected_days else "Выберите дни:"

    await callback.message.edit_text(
        f"🗓 **Новое расписание**\n\n{selected_text}\n\n" "Нажмите на день для выбора/снятия выбора:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_SCHEDULE_TOGGLE_DAY:"))
async def handle_schedule_toggle_day(callback: CallbackQuery, state: FSMContext):
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
    
    # Возвращаемся к выбору дней
    await handle_schedule_period_custom(callback, state)


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_DAYS_DONE")
async def handle_schedule_days_done(callback: CallbackQuery, state: FSMContext):
    """Дни выбраны, переходим к выбору времени"""
    data = await state.get_data()
    selected_days = data.get("schedule_selected_days", [])

    if not selected_days:
        await callback.answer("❌ Выберите хотя бы один день", show_alert=True)
        return

    days_names = ", ".join([DAYS_OF_WEEK.get(day, day) for day in selected_days])
    await state.update_data(
        schedule_days_of_week=",".join(selected_days),
        schedule_periodicity=SchedulePeriodicity.DAILY,
    )
    
    await callback.answer(f"✅ Дни выбраны: {days_names}")
    await _show_time_selection(callback, state)


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_PERIOD_BACK")
async def handle_schedule_period_back(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору задания"""
    data = await state.get_data()
    task_type_id = data.get("schedule_task_type_id")
    
    if task_type_id:
        # Возвращаемся к выбору задания
        from aiogram.types import CallbackQuery as FakeCallback
        fake_cb = type('obj', (object,), {
            'data': f'ADMIN_SCHEDULE_TASK_TYPE:{task_type_id}',
            'message': callback.message,
            'from_user': callback.from_user,
            'answer': callback.answer
        })()
        await handle_schedule_task_type_selected(fake_cb, state)
    else:
        await handle_schedule_add_start(callback, state)
    await callback.answer()


async def _show_time_selection(callback: CallbackQuery, state: FSMContext):
    """Показ выбора времени"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    # Предопределённые времена
    times = ["08:00", "09:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
    
    buttons = []
    row = []
    for i, time_str in enumerate(times):
        row.append(
            InlineKeyboardButton(
                text=f"🕐 {time_str}",
                callback_data=f"ADMIN_SCHEDULE_TIME:{time_str}",
            )
        )
        if len(row) == 2 or i == len(times) - 1:
            buttons.append(row)
            row = []

    buttons.append([
        InlineKeyboardButton(
            text="✏️ Ввести своё время",
            callback_data="ADMIN_SCHEDULE_TIME_CUSTOM",
        )
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_SCHEDULE_PERIOD_BACK")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🗓 **Новое расписание**\n\n" "Выберите время отправки:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_SCHEDULE_TIME:"))
async def handle_schedule_time_selected(callback: CallbackQuery, state: FSMContext):
    """Время выбрано из предопределённых"""
    # Исправляем парсинг: удаляем префикс, чтобы получить "HH:MM"
    time_str = callback.data.replace("ADMIN_SCHEDULE_TIME:", "")
    hours, minutes = map(int, time_str.split(":"))
    schedule_time = time(hours, minutes)
    
    await state.update_data(schedule_time=schedule_time)
    await callback.answer(f"✅ Время выбрано: {time_str}")
    await _show_schedule_confirmation(callback, state)


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_TIME_CUSTOM")
async def handle_schedule_time_custom(callback: CallbackQuery, state: FSMContext):
    """Запрос ввода времени"""
    await callback.message.edit_text(
        "🗓 **Новое расписание**\n\n"
        "Введите время в формате HH:MM (например, 09:30):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddScheduleStates.waiting_for_time)
    await callback.answer()


@router.message(AddScheduleStates.waiting_for_time)
async def handle_schedule_time_input(message: Message, state: FSMContext):
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
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
        return

    await state.update_data(schedule_time=schedule_time)
    
    # Показываем подтверждение
    await _show_schedule_confirmation(message, state)


async def _show_schedule_confirmation(message_or_callback, state: FSMContext):
    """Показ окна подтверждения расписания"""
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        # Получаем тип задания
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == data["schedule_task_type_id"])
        )
        task_type = task_type_result.scalar_one()

        # Получаем информацию о ребёнке
        child_result = await session.execute(
            select(User).where(User.id == data["schedule_child_id"])
        )
        child = child_result.scalar_one()

        # Получаем награду за это задание
        reward_result = await session.execute(
            select(ChildTaskReward).where(
                ChildTaskReward.child_id == child.id,
                ChildTaskReward.task_type_id == task_type.id,
            )
        )
        reward = reward_result.scalar_one_or_none()
        reward_text = f"{reward.reward_amount} {reward.currency}" if reward else "не установлена"

        # Формируем информацию о днях
        days_of_week = data["schedule_days_of_week"]
        days_list = days_of_week.split(",")
        if len(days_list) == 7:
            days_text = "Каждый день"
        elif set(days_list) == set(WEEKDAYS.split(",")):
            days_text = "Будни (Пн-Пт)"
        elif set(days_list) == set(WEEKENDS.split(",")):
            days_text = "Выходные (Сб-Вс)"
        elif len(days_list) == 1:
            days_text = DAYS_OF_WEEK.get(days_list[0], days_list[0])
        else:
            days_text = ", ".join([DAYS_OF_WEEK.get(day, day) for day in days_list])

        # Время
        schedule_time: time = data["schedule_time"]
        time_text = schedule_time.strftime("%H:%M")

        # Описание задания
        task_description = task_type.description or "описание не указано"
        execution_time = f"{task_type.execution_time} мин" if task_type.execution_time else "не указано"

        confirmation_text = (
            f"🗓 **Проверьте настройки расписания**\n\n"
            f"👦 **Для кого:** {child.display_name}\n"
            f"📋 **Задание:** {task_type.name}\n"
            f"📝 **Описание:** {task_description}\n"
            f"⏱ **Время выполнения:** {execution_time}\n"
            f"💰 **Награда:** {reward_text}\n"
            f"📅 **Как часто:** {days_text}\n"
            f"🕐 **Во сколько:** {time_text}\n\n"
            f"Бот будет автоматически отправлять напоминание об этом задании "
            f"для {child.display_name} в указанные дни в {time_text}.\n\n"
            f"❓ **Всё верно?**"
        )

        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Да, всё верно - создать",
                    callback_data="ADMIN_SCHEDULE_CONFIRM",
                )
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="ADMIN_SCHEDULES")
            ],
        ]

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Определяем, это Message или CallbackQuery
        from aiogram.types import Message, CallbackQuery
        
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(confirmation_text, reply_markup=keyboard)
            await message_or_callback.answer()
        elif isinstance(message_or_callback, Message):
            await message_or_callback.answer(confirmation_text, reply_markup=keyboard)
        else:
            # Fallback - если передан другой тип
            raise ValueError(f"Неподдерживаемый тип: {type(message_or_callback)}")


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_CONFIRM")
async def handle_schedule_confirm(callback: CallbackQuery, state: FSMContext):
    """Создание расписания"""
    from sqlalchemy import select

    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        child_id = data["schedule_child_id"]
        
        schedule = Schedule(
            task_type_id=data["schedule_task_type_id"],
            periodicity=data["schedule_periodicity"],
            time_of_day=data["schedule_time"],
            days_of_week=data["schedule_days_of_week"],
            target_scope=TargetScope.SPECIFIC_CHILDREN,  # Для одного ребёнка
            target_children_ids=[child_id],  # Список с одним ребёнком
            is_active=True,
        )
        session.add(schedule)
        await session.commit()
        await session.refresh(schedule)

        # Получаем информацию для отображения
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()

        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == data["schedule_task_type_id"])
        )
        task_type = task_type_result.scalar_one()

    # Формируем информацию о днях
    days_of_week = data["schedule_days_of_week"]
    days_list = days_of_week.split(",")
    if len(days_list) == 7:
        days_text = "Каждый день"
    elif set(days_list) == set(WEEKDAYS.split(",")):
        days_text = "Будни (Пн-Пт)"
    elif set(days_list) == set(WEEKENDS.split(",")):
        days_text = "Выходные (Сб-Вс)"
    elif len(days_list) == 1:
        days_text = DAYS_OF_WEEK.get(days_list[0], days_list[0])
    else:
        days_text = ", ".join([DAYS_OF_WEEK.get(day, day) for day in days_list])

    time_text = data["schedule_time"].strftime("%H:%M")

    await callback.answer("✅ Расписание создано!", show_alert=True)
    await callback.message.edit_text(
        f"✅ **Расписание успешно создано!**\n\n"
        f"📋 **Расписание #{schedule.id}**\n"
        f"📌 **Задание:** {task_type.name}\n"
        f"👦 **Ребёнок:** {child.display_name}\n"
        f"🕐 **Время:** {time_text}\n"
        f"📅 **Дни:** {days_text}\n\n"
        f"Бот будет автоматически отправлять напоминания по этому графику.",
        reply_markup=get_admin_schedules_menu(),
    )
    await state.clear()


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULE_LIST")
async def handle_schedule_list(callback: CallbackQuery):
    """Список всех расписаний"""
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).order_by(Schedule.created_at.desc())
        )
        schedules = result.scalars().all()

        if not schedules:
            text = "🗓 **Список расписаний**\n\n" "Расписания ещё не созданы."
            keyboard = get_admin_schedules_menu()
        else:
            lines = ["🗓 **Список расписаний**\n"]
            buttons = []

            for schedule in schedules:
                status = "✅ active" if schedule.is_active else "❌ inactive"
                
                # Дни недели
                days_list = schedule.days_of_week.split(",")
                if len(days_list) == 7:
                    days_text = "Каждый день"
                elif days_list == WEEKDAYS.split(","):
                    days_text = "Будни"
                elif days_list == WEEKENDS.split(","):
                    days_text = "Выходные"
                else:
                    days_text = ", ".join([DAYS_OF_WEEK.get(day, day) for day in days_list[:3]])
                    if len(days_list) > 3:
                        days_text += f" и ещё {len(days_list) - 3}"

                # Дети
                if schedule.target_scope == TargetScope.ALL_CHILDREN:
                    children_text = "Все дети"
                else:
                    if schedule.target_children_ids:
                        children_result = await session.execute(
                            select(User).where(User.id.in_(schedule.target_children_ids))
                        )
                        children = children_result.scalars().all()
                        children_text = ", ".join([child.display_name for child in children[:2]])
                        if len(children) > 2:
                            children_text += f" и ещё {len(children) - 2}"
                    else:
                        children_text = "Нет детей"

                time_text = schedule.time_of_day.strftime("%H:%M")
                
                lines.append(
                    f"📋 #{schedule.id} {schedule.task_type.name}\n"
                    f"   {days_text}, {time_text}, {children_text} — {status}"
                )
                
                # Кнопка выключения/включения
                action_text = "🚫 Выключить" if schedule.is_active else "✅ Включить"
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{action_text} #{schedule.id}",
                        callback_data=f"ADMIN_SCHEDULE_TOGGLE:{schedule.id}",
                    )
                ])

            text = "\n".join(lines)

            # Кнопка "Назад"
            buttons.append([
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_SCHEDULES")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_SCHEDULE_TOGGLE:"))
async def handle_schedule_toggle(callback: CallbackQuery):
    """Переключение активности расписания"""
    schedule_id = int(callback.data.split(":")[1])
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).where(Schedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            await callback.answer("Расписание не найдено", show_alert=True)
            return

        schedule.is_active = not schedule.is_active
        await session.commit()

    action = "включено" if schedule.is_active else "выключено"
    await callback.answer(f"Расписание #{schedule_id} {action}", show_alert=True)

    # Обновляем список
    await handle_schedule_list(callback)


@router.callback_query(StateFilter(AddScheduleStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_schedule_add_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления расписания"""
    await state.clear()
    await callback.message.edit_text(
        "🗓 **Расписания**\n\n" "Выберите действие:",
        reply_markup=get_admin_schedules_menu(),
    )
    await callback.answer("Добавление отменено")

