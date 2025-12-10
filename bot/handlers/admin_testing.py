"""
Обработчики для тестирования работы бота в чате.
"""
import logging
from decimal import Decimal

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import FAMILY_CHAT_ID
from bot.keyboards.admin import ADMIN_BACK_MAIN, get_back_button_menu
from bot.middleware.auth import AdminMiddleware
from db.database import AsyncSessionLocal
from db.models import ChildTaskReward, TaskType, User, UserRole
from sqlalchemy import select

router = Router()
logger = logging.getLogger(__name__)

router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
from bot.middleware.auto_delete import AutoDeleteMiddleware
router.message.middleware(AutoDeleteMiddleware())


@router.callback_query(lambda c: c.data == "ADMIN_TESTING")
async def handle_testing_menu(callback: CallbackQuery):
    """Меню тестирования"""
    text = (
        "🧪 **Тестирование отправки уведомлений**\n\n"
        "Здесь вы можете протестировать, как бот отправляет задания детям.\n\n"
        "⚠️ **Важно:**\n"
        "• Если настроен семейный чат (`FAMILY_CHAT_ID`), сообщения отправляются туда\n"
        "• Если нет, сообщения отправляются в личные сообщения ребёнка\n"
        "• Для личных сообщений ребёнок должен отправить `/start` боту\n\n"
        "Выберите ребёнка для тестового уведомления:"
    )
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = result.scalars().all()
        
        if not children:
            await callback.message.edit_text(
                "❌ Нет активных детей. Сначала добавьте ребёнка через меню 👦 Дети.",
                reply_markup=get_back_button_menu(),
            )
            await callback.answer()
            return
        
        buttons = []
        for child in children:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👦 {child.display_name}",
                    callback_data=f"ADMIN_TEST_CHILD:{child.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_TEST_CHILD:"))
async def handle_test_child_selected(callback: CallbackQuery, state: FSMContext):
    """Ребёнок выбран для тестирования, выбираем задание"""
    child_id = int(callback.data.split(":")[1])
    await state.update_data(test_child_id=child_id)
    
    async with AsyncSessionLocal() as session:
        # Получаем информацию о ребёнке
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()
        
        # Получаем список типов заданий
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.is_active == True)
        )
        task_types = task_type_result.scalars().all()
        
        if not task_types:
            await callback.message.edit_text(
                f"❌ Нет активных типов заданий. Сначала создайте тип задания через меню 💰 Ставки.",
                reply_markup=get_back_button_menu(),
            )
            await callback.answer()
            return
        
        text = (
            f"🧪 **Тестирование**\n\n"
            f"Выбран ребёнок: **{child.display_name}**\n\n"
            f"Выберите тип задания для тестового уведомления:"
        )
        
        buttons = []
        for task_type in task_types:
            buttons.append([
                InlineKeyboardButton(
                    text=f"📋 {task_type.name}",
                    callback_data=f"ADMIN_TEST_TASK_TYPE:{task_type.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_TESTING"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(f"✅ Выбран ребёнок: {child.display_name}")


@router.callback_query(lambda c: c.data.startswith("ADMIN_TEST_TASK_TYPE:"))
async def handle_test_task_type_selected(callback: CallbackQuery, state: FSMContext):
    """Тип задания выбран, отправляем тестовое сообщение"""
    task_type_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    child_id = data["test_child_id"]
    
    async with AsyncSessionLocal() as session:
        # Получаем информацию о ребёнке
        child_result = await session.execute(
            select(User).where(User.id == child_id)
        )
        child = child_result.scalar_one()
        
        # Получаем тип задания
        task_type_result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = task_type_result.scalar_one()
        
        # Получаем награду
        reward_result = await session.execute(
            select(ChildTaskReward).where(
                ChildTaskReward.child_id == child_id,
                ChildTaskReward.task_type_id == task_type_id,
            )
        )
        reward = reward_result.scalar_one_or_none()
        reward_amount = reward.reward_amount if reward else Decimal("0.00")
        currency = reward.currency if reward else "ARS"
        
        # Формируем текст сообщения (как в scheduler/jobs.py)
        message_text = (
            f"🧪 **ТЕСТОВОЕ УВЕДОМЛЕНИЕ**\n\n"
            f"{child.display_name}, твоё задание на сегодня:\n"
            f"📖 {task_type.name}\n"
            f"Награда: {reward_amount} {currency}\n\n"
            f"Когда выполнишь — нажми кнопку ниже и "
            f"(если нужно) пришли фото/видео **ответом на это сообщение**."
        )
        
        # Определяем, куда отправлять
        from bot.main import Bot  # Получаем bot instance через диспетчер
        from aiogram import Bot as AiogramBot
        from bot.config import BOT_TOKEN
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        
        bot = AiogramBot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # Получаем клавиатуру для задания
        from bot.keyboards.inline import get_task_completion_keyboard
        keyboard = get_task_completion_keyboard()
        
        # Определяем, куда отправлять
        # Если настроен семейный чат, отправляем туда (предпочтительно)
        if FAMILY_CHAT_ID:
            chat_id = FAMILY_CHAT_ID
            chat_type = "семейный чат"
            fallback_to_pm = False
        else:
            # Иначе пытаемся отправить в личку ребёнка
            if not child.telegram_user_id:
                await callback.answer(
                    f"❌ У ребёнка {child.display_name} не указан Telegram ID.\n\n"
                    f"Добавьте его через меню 👦 Дети.",
                    show_alert=True
                )
                return
            chat_id = child.telegram_user_id
            chat_type = "личные сообщения"
            fallback_to_pm = True
        
        try:
            # Отправляем сообщение
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=keyboard,
            )
            
            await callback.answer(
                f"✅ Тестовое сообщение отправлено в {chat_type}!\n"
                f"Chat ID: {chat_id}",
                show_alert=True
            )
            
            # Показываем информацию об отправке
            result_text = (
                f"✅ **Тестовое сообщение отправлено!**\n\n"
                f"👦 Ребёнок: {child.display_name}\n"
                f"📋 Задание: {task_type.name}\n"
                f"💰 Награда: {reward_amount} {currency}\n"
                f"💬 Отправлено в: {chat_type}\n"
                f"🆔 Chat ID: {chat_id}\n"
                f"📝 Message ID: {sent_message.message_id}\n\n"
                f"Проверьте чат, чтобы убедиться, что сообщение получено."
            )
            
            buttons = [
                [
                    InlineKeyboardButton(
                        text="🔄 Отправить ещё раз",
                        callback_data=f"ADMIN_TEST_CHILD:{child_id}",
                    )
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_TESTING"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)
                ],
            ]
            
            keyboard_back = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.edit_text(result_text, reply_markup=keyboard_back)
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Проверяем, это ошибка "can't initiate conversation"
            if "can't initiate conversation" in error_msg or "forbidden" in error_msg:
                if fallback_to_pm:
                    # Если пытались отправить в личку и получили ошибку, предлагаем использовать семейный чат
                    error_text = (
                        f"❌ **Не удалось отправить в личные сообщения**\n\n"
                        f"**Причина:** Ребёнок {child.display_name} не начинал разговор с ботом.\n\n"
                        f"**Решение:**\n"
                        f"1. Попросите ребёнка отправить `/start` боту в личные сообщения, ИЛИ\n"
                        f"2. Настройте семейный чат (`FAMILY_CHAT_ID` в .env) и добавьте бота туда\n\n"
                        f"**Важно:** В Telegram боты не могут первыми писать пользователям. "
                        f"Пользователь должен отправить `/start` боту."
                    )
                else:
                    # Если это семейный чат, значит бот не админ или чат неправильный
                    error_text = (
                        f"❌ **Не удалось отправить в семейный чат**\n\n"
                        f"**Возможные причины:**\n"
                        f"1. Бот не добавлен в чат с ID {FAMILY_CHAT_ID}\n"
                        f"2. Бот не является администратором чата\n"
                        f"3. Неправильный Chat ID\n\n"
                        f"**Решение:**\n"
                        f"1. Добавьте бота в групповой чат\n"
                        f"2. Сделайте бота администратором\n"
                        f"3. Убедитесь, что Chat ID правильный"
                    )
            else:
                # Другая ошибка
                error_text = (
                    f"❌ **Ошибка при отправке**\n\n"
                    f"**Ошибка:** {str(e)}\n\n"
                    f"Проверьте логи бота для получения дополнительной информации."
                )
            
            logger.error(f"Ошибка при отправке тестового сообщения: {e}", exc_info=True)
            
            buttons = [
                [
                    InlineKeyboardButton(
                        text="🔄 Попробовать ещё раз",
                        callback_data=f"ADMIN_TEST_CHILD:{child_id}",
                    )
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_TESTING"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)
                ],
            ]
            keyboard_error = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(error_text, reply_markup=keyboard_error)
            await callback.answer("❌ Ошибка при отправке", show_alert=True)
        
        await state.clear()

