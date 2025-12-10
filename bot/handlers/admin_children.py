"""
Обработчики для управления детьми.
"""
import asyncio
import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.fsm_states import AddChildStates
from bot.keyboards.admin import get_admin_children_menu, get_back_button_menu
from db.database import AsyncSessionLocal
from db.models import User, UserRole

router = Router()
logger = logging.getLogger(__name__)

# Применяем middleware для проверки прав админа
from bot.middleware.auth import AdminMiddleware
from bot.middleware.auto_delete import AutoDeleteMiddleware

router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
router.message.middleware(AutoDeleteMiddleware())


@router.callback_query(lambda c: c.data == "ADMIN_CHILD_ADD")
async def handle_child_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало диалога добавления ребёнка"""
    await callback.message.edit_text(
        "➕ **Добавить ребёнка**\n\n"
        "Введите имя ребёнка:",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddChildStates.waiting_for_name)
    await callback.answer()


@router.callback_query(StateFilter(AddChildStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_child_add_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления ребёнка"""
    await state.clear()
    from bot.keyboards.admin import get_admin_children_menu
    await callback.message.edit_text(
        "👦 **Дети**\n\n" "Выберите действие:",
        reply_markup=get_admin_children_menu(),
    )
    await callback.answer("Добавление отменено")

@router.message(AddChildStates.waiting_for_name)
async def handle_child_name(message: Message, state: FSMContext):
    """Обработка имени ребёнка"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    name = message.text.strip()
    if not name or len(name) > 100:
        error_msg = await message.answer(
            "❌ Имя должно быть от 1 до 100 символов. Попробуйте снова:",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
        return

    await state.update_data(child_name=name)
    await message.answer(
        f"✅ Имя сохранено: {name}\n\n" "Теперь введите возраст ребёнка (число):",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddChildStates.waiting_for_age)


@router.message(AddChildStates.waiting_for_age)
async def handle_child_age(message: Message, state: FSMContext):
    """Обработка возраста ребёнка"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        age = int(message.text.strip())
        if age < 0 or age > 18:
            error_msg = await message.answer(
                "❌ Возраст должен быть от 0 до 18 лет. Попробуйте снова:",
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
            "❌ Пожалуйста, введите число (возраст):",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
        return

    await state.update_data(child_age=age)
    await message.answer(
        f"✅ Возраст сохранён: {age} лет\n\n"
        f"Теперь введите Telegram ID ребёнка (число).\n"
        f"Чтобы узнать ID, попросите ребёнка написать боту @userinfobot или используйте команду /start в боте.",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddChildStates.waiting_for_telegram_id)


@router.message(AddChildStates.waiting_for_telegram_id)
async def handle_child_telegram_id(message: Message, state: FSMContext):
    """Обработка Telegram ID ребёнка"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        telegram_user_id = int(message.text.strip())
        if telegram_user_id <= 0:
            raise ValueError
    except ValueError:
        error_msg = await message.answer(
            "❌ Telegram ID должен быть положительным числом. Попробуйте снова:",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
        return

    data = await state.get_data()
    child_name = data.get("child_name")
    age = data.get("child_age")

    # Проверка, не существует ли уже пользователь с таким Telegram ID
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        
        existing_result = await session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        existing_user = existing_result.scalar_one_or_none()
        
        if existing_user:
            error_msg = await message.answer(
                f"❌ Пользователь с Telegram ID {telegram_user_id} уже существует в системе.\n"
                f"Проверьте правильность ID и попробуйте снова:",
                reply_markup=get_back_button_menu(),
            )
            await asyncio.sleep(5)
            try:
                await error_msg.delete()
            except Exception:
                pass
            return

        # Сохранение ребёнка в БД
        child = User(
            telegram_user_id=telegram_user_id,
            role=UserRole.CHILD,
            display_name=child_name,
            age=age,
            is_active=True,
        )
        session.add(child)
        await session.commit()
        await session.refresh(child)

    # Показываем успешное сообщение с кнопкой просмотра списка
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    view_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📃 Посмотреть список детей",
                    callback_data="ADMIN_CHILD_LIST",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_CHILDREN"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
            ]
        ]
    )
    
    await message.answer(
        f"✅ **Ребёнок успешно добавлен!**\n\n"
        f"👦 Имя: {child_name}\n"
        f"🎂 Возраст: {age} лет\n"
        f"🆔 Telegram ID: {telegram_user_id}\n"
        f"🆔 ID в системе: {child.id}\n\n"
        f"Ребёнок может начать пользоваться ботом, отправив /start",
        reply_markup=view_button,
    )
    await state.clear()


@router.callback_query(lambda c: c.data == "ADMIN_CHILD_LIST")
async def handle_child_list(callback: CallbackQuery):
    """Список всех детей с кнопками удаления"""
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True).order_by(User.created_at.desc())
        )
        children = result.scalars().all()

        if not children:
            text = "👦 **Список детей**\n\n" "Дети ещё не добавлены."
            keyboard = get_admin_children_menu()
        else:
            lines = ["👦 **Список детей**\n"]
            buttons = []
            
            for child in children:
                status = "✅ active" if child.is_active else "❌ inactive"
                age_text = f", {child.age} лет" if child.age else ""
                telegram_info = (
                    f" (Telegram ID: {child.telegram_user_id})"
                    if child.telegram_user_id
                    else " (Telegram не привязан)"
                )
                lines.append(
                    f"👦 **{child.display_name}**{age_text} — {status}{telegram_info}"
                )
                # Кнопка удаления для каждого ребёнка
                buttons.append([
                    InlineKeyboardButton(
                        text=f"🗑 Удалить {child.display_name}",
                        callback_data=f"ADMIN_CHILD_DELETE:{child.id}",
                    )
                ])

            text = "\n".join(lines)
            
            # Кнопка "Добавить ребёнка"
            buttons.append([
                InlineKeyboardButton(
                    text="➕ Добавить ребёнка",
                    callback_data="ADMIN_CHILD_ADD",
                )
            ])
            
            # Кнопка "Назад"
            buttons.append([
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_CHILDREN"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_CHILD_DELETE:"))
async def handle_child_delete(callback: CallbackQuery):
    """Полное удаление ребёнка и всех связанных данных"""
    child_id = int(callback.data.split(":")[1])
    from sqlalchemy import select, delete
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from db.models import Task, TaskMedia, ChildTaskReward

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == child_id, User.role == UserRole.CHILD)
        )
        child = result.scalar_one_or_none()

        if not child:
            await callback.answer("Ребёнок не найден", show_alert=True)
            return

        child_name = child.display_name
        
        # Получаем все задания ребенка
        tasks_result = await session.execute(
            select(Task).where(Task.child_id == child_id)
        )
        tasks = tasks_result.scalars().all()
        
        # Удаляем все медиа заданий ребенка
        task_ids = [task.id for task in tasks]
        if task_ids:
            await session.execute(
                delete(TaskMedia).where(TaskMedia.task_id.in_(task_ids))
            )
            logger.info(f"Deleted {len(task_ids)} TaskMedia records for child {child_id}")
        
        # Удаляем все задания ребенка
        if tasks:
            await session.execute(
                delete(Task).where(Task.child_id == child_id)
            )
            logger.info(f"Deleted {len(tasks)} Task records for child {child_id}")
        
        # Удаляем все ставки (награды) для ребенка
        await session.execute(
            delete(ChildTaskReward).where(ChildTaskReward.child_id == child_id)
        )
        logger.info(f"Deleted ChildTaskReward records for child {child_id}")
        
        # Удаляем самого ребенка
        await session.delete(child)
        await session.commit()
        
        logger.info(f"Completely deleted child {child_id} ({child_name}) and all related data")

    await callback.answer(f"Ребёнок {child_name} и вся связанная информация полностью удалены", show_alert=True)
    
    # Обновляем список
    await handle_child_list(callback)

