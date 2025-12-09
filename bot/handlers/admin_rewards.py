"""
Обработчики для управления ставками и типами заданий.
"""
import asyncio
import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.fsm_states import AddTaskTypeStates, SetRewardStates
from bot.keyboards.admin import get_admin_rewards_menu, get_back_button_menu
from db.database import AsyncSessionLocal
from db.models import ChildTaskReward, TaskCategory, TaskType, User, UserRole
from decimal import Decimal

router = Router()
logger = logging.getLogger(__name__)

# Применяем middleware для проверки прав админа
from bot.middleware.auth import AdminMiddleware
from bot.middleware.auto_delete import AutoDeleteMiddleware

router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
router.message.middleware(AutoDeleteMiddleware())


# ========== Обработчики для типов заданий ==========

@router.callback_query(lambda c: c.data == "ADMIN_ADD_TASK_TYPE")
async def handle_task_type_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало диалога добавления типа задания"""
    await callback.message.edit_text(
        "➕ **Добавить тип задания**\n\n" "Введите название задания:",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_name)
    await callback.answer()


@router.callback_query(StateFilter(AddTaskTypeStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_task_type_add_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления типа задания"""
    await state.clear()
    from bot.keyboards.admin import get_admin_rewards_menu
    await callback.message.edit_text(
        "💰 **Ставки**\n\n" "Выберите действие:",
        reply_markup=get_admin_rewards_menu(),
    )
    await callback.answer("Добавление отменено")

@router.callback_query(StateFilter(SetRewardStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_reward_set_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена установки ставки"""
    await state.clear()
    from bot.keyboards.admin import get_admin_rewards_menu
    await callback.message.edit_text(
        "💰 **Ставки**\n\n" "Выберите действие:",
        reply_markup=get_admin_rewards_menu(),
    )
    await callback.answer("Установка ставки отменена")

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
        # Удаляем сообщение об ошибке через 5 секунд
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
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
    
    # Предлагаем выбрать категорию
    categories_text = "\n".join([f"{i+1}. {cat.value}" for i, cat in enumerate(TaskCategory)])
    await message.answer(
        f"✅ Описание сохранено.\n\n"
        f"Выберите категорию задания (введите номер):\n\n"
        f"{categories_text}",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_category)


@router.message(AddTaskTypeStates.waiting_for_category)
async def handle_task_type_category(message: Message, state: FSMContext):
    """Обработка категории задания"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        category_num = int(message.text.strip())
        categories = list(TaskCategory)
        if category_num < 1 or category_num > len(categories):
            raise ValueError
        category = categories[category_num - 1]
    except (ValueError, IndexError):
        error_msg = await message.answer(
            "❌ Пожалуйста, введите номер категории от 1 до 5:",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
        return

    await state.update_data(task_type_category=category)
    await message.answer(
        f"✅ Категория выбрана: {category.value}\n\n"
        f"Введите время выполнения в минутах (число, можно пропустить, отправив '-'):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_execution_time)


@router.message(AddTaskTypeStates.waiting_for_execution_time)
async def handle_task_type_execution_time(message: Message, state: FSMContext):
    """Обработка времени выполнения"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    execution_time = None
    if message.text.strip() != "-":
        try:
            execution_time = int(message.text.strip())
            if execution_time < 1:
                error_msg = await message.answer(
                    "❌ Время выполнения должно быть положительным числом. Попробуйте снова:",
                    reply_markup=get_back_button_menu(),
                )
                await asyncio.sleep(5)
                try:
                    await error_msg.delete()
                except Exception:
                    pass
                return
        except ValueError:
            error_msg = await message.answer(
                "❌ Пожалуйста, введите число (минуты) или '-' для пропуска:",
                reply_markup=get_back_button_menu(),
            )
            await asyncio.sleep(5)
            try:
                await error_msg.delete()
            except Exception:
                pass
            return

    await state.update_data(task_type_execution_time=execution_time)
    
    await message.answer(
        f"✅ Время выполнения сохранено: {execution_time or 'не указано'} минут\n\n"
        f"Нужно ли прикладывать отчёт по выполнению? (да/нет):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_requires_media)


@router.message(AddTaskTypeStates.waiting_for_requires_media)
async def handle_task_type_requires_media(message: Message, state: FSMContext):
    """Обработка необходимости отчёта"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    text = message.text.strip().lower()
    requires_media = text in ["да", "yes", "д", "y", "1", "true"]

    await state.update_data(task_type_requires_media=requires_media)
    
    await message.answer(
        f"✅ Отчёт: {'требуется' if requires_media else 'не требуется'}\n\n"
        f"Введите частотность выполнения (daily/weekly/custom или '-' для пропуска):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_frequency)


@router.message(AddTaskTypeStates.waiting_for_frequency)
async def handle_task_type_frequency(message: Message, state: FSMContext):
    """Обработка частотности выполнения"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    frequency = message.text.strip() if message.text.strip() != "-" else None
    if frequency and frequency not in ["daily", "weekly", "custom"]:
        error_msg = await message.answer(
            "❌ Частотность должна быть: daily, weekly, custom или '-'. Попробуйте снова:",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
        return

    data = await state.get_data()

    # Сохранение типа задания в БД
    async with AsyncSessionLocal() as session:
        # Определяем категорию по умолчанию, если не указана
        category = data.get("task_type_category", TaskCategory.OTHER)
        
        task_type = TaskType(
            name=data["task_type_name"],
            description=data.get("task_type_description"),
            category=category,
            execution_time=data.get("task_type_execution_time"),
            requires_media=data.get("task_type_requires_media", False),
            frequency=frequency,
            is_active=True,
        )
        session.add(task_type)
        await session.commit()
        await session.refresh(task_type)

    # Показываем успешное сообщение с кнопкой просмотра списка
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    view_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Посмотреть список заданий",
                    callback_data="ADMIN_TASK_TYPE_LIST",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS")
            ]
        ]
    )
    
    await message.answer(
        f"✅ **Тип задания успешно создан!**\n\n"
        f"📋 Название: {task_type.name}\n"
        f"📝 Описание: {task_type.description or 'не указано'}\n"
        f"📂 Категория: {task_type.category.value}\n"
        f"⏱ Время выполнения: {task_type.execution_time or 'не указано'} минут\n"
        f"📸 Отчёт: {'требуется' if task_type.requires_media else 'не требуется'}\n"
        f"🔄 Частотность: {task_type.frequency or 'не указана'}\n"
        f"🆔 ID: {task_type.id}",
        reply_markup=view_button,
    )
    await state.clear()


# ========== Обработчики для ставок ==========

@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_CHILD_SELECT")
async def handle_rewards_by_child_select(callback: CallbackQuery, state: FSMContext):
    """Выбор ребёнка для установки ставки"""
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
            await callback.answer()
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
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            "💰 **Установка ставки по ребёнку**\n\n" "Выберите ребёнка:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD:"))
async def handle_reward_child_selected(callback: CallbackQuery, state: FSMContext):
    """Ребёнок выбран, теперь выбираем тип задания"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(reward_child_id=child_id)
    
    # Показываем подтверждение выбора
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()
    await callback.answer(f"✅ Выбран ребёнок: {child.display_name}")

    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Получаем имя ребёнка
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one_or_none()
        if not child:
            await callback.answer("Ребёнок не найден", show_alert=True)
            return

        # Получаем типы заданий
        task_types_result = await session.execute(
            select(TaskType).where(TaskType.is_active == True)
        )
        task_types = task_types_result.scalars().all()

        if not task_types:
            await callback.message.edit_text(
                "❌ Нет активных типов заданий. Сначала создайте тип задания.",
                reply_markup=get_admin_rewards_menu(),
            )
            await callback.answer()
            return

        # Формируем список заданий кнопками
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
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"💰 **Установка ставки для {child.display_name}**\n\n" "Выберите тип задания:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_TASKTYPE_SELECT")
async def handle_rewards_by_task_type_select(callback: CallbackQuery, state: FSMContext):
    """Выбор типа задания для установки ставки"""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Получаем типы заданий
        task_types_result = await session.execute(
            select(TaskType).where(TaskType.is_active == True)
        )
        task_types = task_types_result.scalars().all()

        if not task_types:
            await callback.message.edit_text(
                "❌ Нет активных типов заданий. Сначала создайте тип задания.",
                reply_markup=get_admin_rewards_menu(),
            )
            await callback.answer()
            return

        # Формируем список заданий кнопками
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
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            "💰 **Установка ставки по заданию**\n\n" "Выберите тип задания:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE_FIRST:"))
async def handle_reward_task_type_first_selected(callback: CallbackQuery, state: FSMContext):
    """Тип задания выбран первым, теперь выбираем ребёнка"""
    task_type_id = int(callback.data.split(":")[1])
    await state.update_data(reward_task_type_id=task_type_id)
    
    # Показываем подтверждение выбора
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one()
    await callback.answer(f"✅ Выбрано задание: {task_type.name}")

    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Получаем имя задания
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one_or_none()
        if not task_type:
            await callback.answer("Тип задания не найден", show_alert=True)
            return

        # Получаем детей
        children_result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = children_result.scalars().all()

        if not children:
            await callback.message.edit_text(
                "❌ Нет активных детей. Сначала добавьте ребёнка.",
                reply_markup=get_admin_rewards_menu(),
            )
            await callback.answer()
            return

        # Формируем список детей кнопками
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
            InlineKeyboardButton(text="⬅️ Назад в меню ставок", callback_data="ADMIN_REWARDS")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"💰 **Установка ставки для {task_type.name}**\n\n" "Выберите ребёнка:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD_SECOND:"))
async def handle_reward_child_second_selected(callback: CallbackQuery, state: FSMContext):
    """Ребёнок выбран вторым, запрашиваем сумму"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(reward_child_id=child_id)
    
    # Показываем подтверждение выбора
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()
    await callback.answer(f"✅ Выбран ребёнок: {child.display_name}")

    await callback.message.edit_text(
        "💰 **Установка ставки**\n\n"
        "Введите сумму вознаграждения (число, например: 1000):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(SetRewardStates.waiting_for_amount)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE:"))
async def handle_reward_task_type_selected(callback: CallbackQuery, state: FSMContext):
    """Тип задания выбран, запрашиваем сумму"""
    task_type_id = int(callback.data.split(":")[1])
    await state.update_data(reward_task_type_id=task_type_id)
    
    # Показываем подтверждение выбора
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one()
    await callback.answer(f"✅ Выбрано задание: {task_type.name}")

    await callback.message.edit_text(
        "💰 **Установка ставки**\n\n"
        "Введите сумму вознаграждения (число, например: 1000):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(SetRewardStates.waiting_for_amount)
    await callback.answer()


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
            await asyncio.sleep(5)
            try:
                await error_msg.delete()
            except Exception:
                pass
            return
    except (ValueError, Exception):
        error_msg = await message.answer(
            "❌ Пожалуйста, введите число (сумма вознаграждения):",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
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
        f"✅ **Ставка {status_text}!**\n\n"
        f"👦 Ребёнок: {child.display_name}\n"
        f"📋 Задание: {task_type.name}\n"
        f"💰 Сумма: {amount} ARS",
        reply_markup=get_admin_rewards_menu(),
    )
    await state.clear()

