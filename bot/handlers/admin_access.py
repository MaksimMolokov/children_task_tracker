"""
Обработчики для управления доступами (админы и пользователи).
"""
import asyncio
import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, delete

from bot.handlers.fsm_states import AddUserStates
from bot.keyboards.admin import ADMIN_BACK_MAIN, get_back_button_menu
from db.database import AsyncSessionLocal
from db.models import User, UserRole, Task, TaskMedia, ChildTaskReward

router = Router()
logger = logging.getLogger(__name__)

# Применяем middleware для проверки прав админа
from bot.middleware.auth import AdminMiddleware
from bot.middleware.auto_delete import AutoDeleteMiddleware

router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
router.message.middleware(AutoDeleteMiddleware())


@router.callback_query(lambda c: c.data == "ADMIN_ACCESS")
async def handle_access_menu(callback: CallbackQuery):
    """Главное меню раздела 'Доступы'"""
    from bot.keyboards.admin import get_admin_access_menu
    
    await callback.message.edit_text(
        "🔐 Доступы\n\n"
        "Управление пользователями системы:\n"
        "- Админы: могут создавать задания, просматривать отчеты, редактировать информацию\n"
        "- Пользователи: получают задания и выполняют их\n\n"
        "Выберите действие:",
        reply_markup=get_admin_access_menu(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_ACCESS_LIST")
async def handle_access_list(callback: CallbackQuery):
    """Список всех пользователей (админов и детей)"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.is_active == True).order_by(User.role, User.created_at.desc())
        )
        users = result.scalars().all()
        
        if not users:
            text = "🔐 Список пользователей\n\nПользователи ещё не добавлены."
            keyboard = get_admin_access_menu()
        else:
            lines = ["🔐 Список пользователей\n"]
            buttons = []
            
            # Группируем по ролям
            admins = [u for u in users if u.role == UserRole.ADMIN]
            children = [u for u in users if u.role == UserRole.CHILD]
            
            if admins:
                lines.append("\n👨‍💼 Администраторы:")
                for admin in admins:
                    telegram_info = (
                        f" (Telegram ID: {admin.telegram_user_id})"
                        if admin.telegram_user_id
                        else " (Telegram не привязан)"
                    )
                    lines.append(f"  • {admin.display_name}{telegram_info}")
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"🗑 Удалить {admin.display_name}",
                            callback_data=f"ADMIN_USER_DELETE:{admin.id}",
                        )
                    ])
            
            if children:
                lines.append("\n👦 Пользователи (дети):")
                for child in children:
                    age_text = f", {child.age} лет" if child.age else ""
                    telegram_info = (
                        f" (Telegram ID: {child.telegram_user_id})"
                        if child.telegram_user_id
                        else " (Telegram не привязан)"
                    )
                    lines.append(f"  • {child.display_name}{age_text}{telegram_info}")
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"🗑 Удалить {child.display_name}",
                            callback_data=f"ADMIN_USER_DELETE:{child.id}",
                        )
                    ])
            
            text = "\n".join(lines)
            
            # Кнопка "Добавить пользователя"
            buttons.append([
                InlineKeyboardButton(
                    text="➕ Добавить пользователя",
                    callback_data="ADMIN_USER_ADD",
                )
            ])
            
            # Кнопка "Назад"
            buttons.append([
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_ACCESS"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_USER_ADD")
async def handle_user_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало диалога добавления пользователя"""
    await callback.message.edit_text(
        "➕ Добавить пользователя\n\n"
        "Введите имя пользователя:",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddUserStates.waiting_for_name)
    await callback.answer()


@router.callback_query(StateFilter(AddUserStates), lambda c: c.data == "ADMIN_BACK_MAIN")
async def handle_user_add_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления пользователя"""
    await state.clear()
    from bot.keyboards.admin import get_admin_access_menu
    await callback.message.edit_text(
        "🔐 Доступы\n\n"
        "Управление пользователями системы.\n\n"
        "Выберите действие:",
        reply_markup=get_admin_access_menu(),
    )
    await callback.answer("Добавление отменено")


@router.message(AddUserStates.waiting_for_name)
async def handle_user_name(message: Message, state: FSMContext):
    """Обработка имени пользователя"""
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

    await state.update_data(user_name=name)
    await message.answer(
        f"✅ Имя сохранено: {name}\n\n"
        f"Теперь введите Telegram ID пользователя (число).\n\n"
        f"⚠️ Важно: Telegram ID необходим для:\n"
        f"- Отправки сообщений пользователю\n"
        f"- Идентификации пользователя в системе\n\n"
        f"Чтобы узнать ID, попросите пользователя написать боту @userinfobot или используйте команду /start в боте.",
        reply_markup=get_back_button_menu(),
    )
    await state.set_state(AddUserStates.waiting_for_telegram_id)


@router.message(AddUserStates.waiting_for_telegram_id)
async def handle_user_telegram_id(message: Message, state: FSMContext):
    """Обработка Telegram ID пользователя"""
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

    # Проверка, не существует ли уже пользователь с таким Telegram ID
    async with AsyncSessionLocal() as session:
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

    await state.update_data(user_telegram_id=telegram_user_id)
    
    # Предлагаем выбрать роль
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👨‍💼 Админ",
                    callback_data="ADMIN_USER_ROLE:admin"
                ),
                InlineKeyboardButton(
                    text="👦 Пользователь",
                    callback_data="ADMIN_USER_ROLE:child"
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_BACK_MAIN")
            ]
        ]
    )
    
    await message.answer(
        f"✅ Telegram ID сохранён: {telegram_user_id}\n\n"
        f"Выберите роль пользователя:",
        reply_markup=keyboard,
    )
    await state.set_state(AddUserStates.waiting_for_role)


@router.callback_query(AddUserStates.waiting_for_role, lambda c: c.data.startswith("ADMIN_USER_ROLE:"))
async def handle_user_role_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора роли пользователя"""
    role_str = callback.data.split(":")[1]
    role = UserRole.ADMIN if role_str == "admin" else UserRole.CHILD
    
    await state.update_data(user_role=role)
    
    # Если выбрана роль CHILD, запрашиваем возраст (обязательно)
    if role == UserRole.CHILD:
        await callback.message.edit_text(
            f"✅ Роль выбрана: Пользователь (ребенок)\n\n"
            f"Введите возраст ребёнка (число от 1 до 18):",
            reply_markup=get_back_button_menu(),
        )
        await state.set_state(AddUserStates.waiting_for_age)
        await callback.answer()
        return
    
    # Для админа сразу показываем подтверждение
    role_info = (
        "👨‍💼 Администратор имеет права на:\n"
        "• Просмотр отчетов\n"
        "• Создание заданий\n"
        "• Редактирование и удаление информации\n"
        "• Управление пользователями и доступами"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data="ADMIN_USER_CONFIRM"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="ADMIN_USER_CANCEL"
                )
            ]
        ]
    )
    
    data = await state.get_data()
    user_name = data.get("user_name")
    telegram_id = data.get("user_telegram_id")
    
    await callback.message.edit_text(
        f"📋 Подтверждение создания пользователя\n\n"
        f"Имя: {user_name}\n"
        f"Telegram ID: {telegram_id}\n"
        f"Роль: Администратор\n\n"
        f"{role_info}\n\n"
        f"Подтвердите создание:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.message(AddUserStates.waiting_for_age)
async def handle_user_age(message: Message, state: FSMContext):
    """Обработка возраста пользователя (обязательно для роли CHILD)"""
    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        age = int(message.text.strip())
        if age < 1 or age > 18:
            error_msg = await message.answer(
                "❌ Возраст должен быть от 1 до 18 лет. Попробуйте снова:",
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
            "❌ Пожалуйста, введите число (возраст от 1 до 18):",
            reply_markup=get_back_button_menu(),
        )
        await asyncio.sleep(5)
        try:
            await error_msg.delete()
        except Exception:
            pass
        return

    # Сохраняем возраст (обязательное поле)
    await state.update_data(user_age=age)
    
    # Показываем подтверждение с информацией о правах
    role_info = (
        "👦 Пользователь (ребенок) имеет права на:\n"
        "• Получение заданий\n"
        "• Выполнение заданий\n"
        "• Отправку отчетов о выполнении"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data="ADMIN_USER_CONFIRM"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="ADMIN_USER_CANCEL"
                )
            ]
        ]
    )
    
    data = await state.get_data()
    user_name = data.get("user_name")
    telegram_id = data.get("user_telegram_id")
    
    await message.answer(
        f"📋 Подтверждение создания пользователя\n\n"
        f"Имя: {user_name}\n"
        f"Telegram ID: {telegram_id}\n"
        f"Роль: Пользователь (ребенок)\n"
        f"Возраст: {age} лет\n\n"
        f"{role_info}\n\n"
        f"Подтвердите создание:",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data == "ADMIN_USER_CONFIRM")
async def handle_user_create(callback: CallbackQuery, state: FSMContext):
    """Создание пользователя в БД"""
    data = await state.get_data()
    user_name = data.get("user_name")
    telegram_id = data.get("user_telegram_id")
    role = data.get("user_role")
    age = data.get("user_age")  # Для CHILD обязателен, для ADMIN None
    
    # Проверка обязательных полей
    if not all([user_name, telegram_id, role]):
        await callback.answer("Ошибка: не все данные заполнены", show_alert=True)
        await state.clear()
        return
    
    # Для роли CHILD возраст обязателен
    if role == UserRole.CHILD and not age:
        await callback.answer("Ошибка: возраст обязателен для пользователя (ребенка)", show_alert=True)
        await state.clear()
        return
    
    async with AsyncSessionLocal() as session:
        # Проверка на дубликат (на случай если добавили пока ждали)
        existing_result = await session.execute(
            select(User).where(User.telegram_user_id == telegram_id)
        )
        existing_user = existing_result.scalar_one_or_none()
        
        if existing_user:
            await callback.answer(
                f"Пользователь с Telegram ID {telegram_id} уже существует",
                show_alert=True
            )
            await state.clear()
            return
        
        # Создание пользователя
        user = User(
            telegram_user_id=telegram_id,
            role=role,
            display_name=user_name,
            age=age,  # Может быть None
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    role_text = "Администратор" if role == UserRole.ADMIN else "Пользователь (ребенок)"
    age_text = f"\n🎂 Возраст: {age} лет" if age else ""
    
    view_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📃 Посмотреть список пользователей",
                    callback_data="ADMIN_ACCESS_LIST",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_ACCESS"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)
            ]
        ]
    )
    
    success_text = (
        f"✅ Пользователь успешно добавлен!\n\n"
        f"👤 Имя: {user_name}\n"
        f"🆔 Telegram ID: {telegram_id}\n"
        f"👤 Роль: {role_text}{age_text}\n"
        f"🆔 ID в системе: {user.id}\n\n"
        f"Пользователь может начать пользоваться ботом, отправив /start"
    )
    
    await callback.message.edit_text(success_text, reply_markup=view_button)
    await state.clear()
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_USER_CANCEL")
async def handle_user_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена создания пользователя"""
    await state.clear()
    from bot.keyboards.admin import get_admin_access_menu
    await callback.message.edit_text(
        "🔐 Доступы\n\n"
        "Управление пользователями системы.\n\n"
        "Выберите действие:",
        reply_markup=get_admin_access_menu(),
    )
    await callback.answer("Создание отменено")


@router.callback_query(lambda c: c.data.startswith("ADMIN_USER_DELETE:"))
async def handle_user_delete(callback: CallbackQuery):
    """Удаление пользователя и всех связанных данных"""
    user_id = int(callback.data.split(":")[1])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        user_name = user.display_name
        is_child = user.role == UserRole.CHILD
        
        if is_child:
            # Получаем все задания ребенка
            tasks_result = await session.execute(
                select(Task).where(Task.child_id == user_id)
            )
            tasks = tasks_result.scalars().all()
            
            # Удаляем все медиа заданий ребенка
            task_ids = [task.id for task in tasks]
            if task_ids:
                await session.execute(
                    delete(TaskMedia).where(TaskMedia.task_id.in_(task_ids))
                )
                logger.info(f"Deleted {len(task_ids)} TaskMedia records for user {user_id}")
            
            # Удаляем все задания ребенка
            if tasks:
                await session.execute(
                    delete(Task).where(Task.child_id == user_id)
                )
                logger.info(f"Deleted {len(tasks)} Task records for user {user_id}")
            
            # Удаляем все ставки (награды) для ребенка
            await session.execute(
                delete(ChildTaskReward).where(ChildTaskReward.child_id == user_id)
            )
            logger.info(f"Deleted ChildTaskReward records for user {user_id}")
        
        # Удаляем самого пользователя
        await session.delete(user)
        await session.commit()
        
        logger.info(f"Completely deleted user {user_id} ({user_name}) and all related data")

    await callback.answer(f"Пользователь {user_name} и вся связанная информация полностью удалены", show_alert=True)
    
    # Обновляем список
    await handle_access_list(callback)
