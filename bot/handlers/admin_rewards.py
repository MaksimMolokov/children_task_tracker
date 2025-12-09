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
        "➕ **Создать новую карточку задания**\n\n" "Введите название задания:",
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
        "🗂 **Карточки заданий**\n\n" "Выберите действие:",
        reply_markup=get_admin_rewards_menu(),
    )
    await callback.answer("Добавление отменено")

@router.callback_query(StateFilter(SetRewardStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_reward_set_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена установки ставки"""
    await state.clear()
    from bot.keyboards.admin import get_admin_rewards_menu
    await callback.message.edit_text(
        "🗂 **Карточки заданий**\n\n" "Выберите действие:",
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




@router.callback_query(lambda c: c.data.startswith("ADMIN_TT_FREQ:"))
async def handle_task_type_frequency_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора частотности через кнопки"""
    freq_type = callback.data.split(":")[1]
    
    if freq_type == "custom":
        await callback.message.edit_text(
            "✏️ **Введите частотность вручную**\n"
            "(например: 'по будням', 'каждые 3 дня' и т.д.):",
            reply_markup=get_back_button_menu(),
        )
        await callback.answer()
        # Остаемся в том же состоянии, ждем текст
        return

    # Если выбрали готовый вариант
    await state.update_data(task_type_frequency=freq_type)
    
    await callback.message.edit_text(
        "💰 **Стоимость выполнения**\n\n"
        "Введите сумму вознаграждения за это задание (число, например: 1000):",
        reply_markup=get_back_button_menu()
    )
    await state.set_state(AddTaskTypeStates.waiting_for_reward_amount)
    await callback.answer()


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
        await asyncio.sleep(5)
        try: await error_msg.delete()
        except: pass
        return

    # Сохраняем сумму в стейт
    await state.update_data(task_type_reward_amount=amount)

    await message.answer(
        f"✅ Стоимость сохранена: {amount} ARS\n\n"
        f"📸 Нужно ли прикладывать отчёт по выполнению? (да/нет):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddTaskTypeStates.waiting_for_confirmation)


@router.message(AddTaskTypeStates.waiting_for_confirmation)
async def handle_task_type_confirm(message: Message, state: FSMContext):
    """Обработка ответа про отчет и создание задания"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass

    text = message.text.strip().lower()

    # Валидация ответа
    if text not in ["да", "yes", "д", "y", "1", "true", "нет", "no", "н", "n", "0", "false"]:
        error_msg = await message.answer(
            "❌ Пожалуйста, ответьте 'да' или 'нет' на вопрос о необходимости отчёта:",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try: await error_msg.delete()
        except: pass
        return

    requires_media = text in ["да", "yes", "д", "y", "1", "true"]

    data = await state.get_data()
    reward_amount = data["task_type_reward_amount"]

    # Сохранение типа задания в БД
    async with AsyncSessionLocal() as session:
        # Категория по умолчанию
        category = data.get("task_type_category", TaskCategory.OTHER)

        task_type = TaskType(
            name=data["task_type_name"],
            description=data.get("task_type_description"),
            category=category,
            execution_time=data.get("task_type_execution_time"),
            requires_media=requires_media,
            is_active=True,
        )
        session.add(task_type)
        await session.commit()
        await session.refresh(task_type)

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

    text = (
        f"✅ **Карточка задания успешно создана!**\n\n"
        f"📋 **{task_type.name}**\n"
        f"📝 {task_type.description}\n"
        f"⏱ {task_type.execution_time} минут\n"
        f"💰 Стоимость: {reward_amount} ARS\n"
        f"📸 Отчёт: {'требуется' if requires_media else 'не требуется'}\n"
        f"🆔 ID: {task_type.id}"
    )

    await message.answer(text, reply_markup=keyboard)
    await state.clear()






# Удален старый хэндлер
async def handle_task_type_frequency_text(message: Message, state: FSMContext):
    """Обработка ввода частотности вручную (для custom)"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    frequency = message.text.strip()
    if not frequency or len(frequency) > 50:
         error_msg = await message.answer(
            "❌ Слишком длинный текст. Введите кратко (до 50 символов):",
            reply_markup=get_back_button_menu(),
        )
         await asyncio.sleep(5)
         try: await error_msg.delete() 
         except: pass
         return
    
    await state.update_data(task_type_frequency=frequency)

    await message.answer(
        "💰 **Стоимость выполнения**\n\n"
        "Введите сумму вознаграждения за это задание (число, например: 1000):",
        reply_markup=get_back_button_menu()
    )
    await state.set_state(AddTaskTypeStates.waiting_for_reward_amount)


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
        "🗂 **Установка ставки по ребёнку**\n\n" "Выберите ребёнка:",
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
        f"🗂 **Установка ставки для {child.display_name}**\n\n" "Выберите тип задания:",
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
        "🗂 **Установка ставки по заданию**\n\n" "Выберите тип задания:",
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
        f"🗂 **Установка ставки для {task_type.name}**\n\n" "Выберите ребёнка:",
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

