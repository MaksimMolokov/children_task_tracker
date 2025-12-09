"""
Обработчики для управления типами заданий.
"""
import logging

from aiogram import Router
from aiogram.types import CallbackQuery

from bot.keyboards.admin import get_admin_rewards_menu, get_back_button_menu
from bot.middleware.auth import AdminMiddleware
from db.database import AsyncSessionLocal
from db.models import TaskType
from sqlalchemy import select

router = Router()
logger = logging.getLogger(__name__)

router.callback_query.middleware(AdminMiddleware())


@router.callback_query(lambda c: c.data == "ADMIN_TASK_TYPE_LIST")
async def handle_task_type_list(callback: CallbackQuery):
    """Список всех типов заданий с кнопками удаления"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TaskType).where(TaskType.is_active == True).order_by(TaskType.created_at.desc())
        )
        task_types = result.scalars().all()

        if not task_types:
            text = "📋 **Список карточек заданий**\n\n" "Карточки ещё не созданы."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Создать новую карточку",
                        callback_data="ADMIN_ADD_TASK_TYPE",
                    )
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS")
                ]
            ])
        else:
            lines = ["📋 **Список карточек заданий**\n"]
            buttons = []

            for task_type in task_types:
                exec_time = f"{task_type.execution_time} мин" if task_type.execution_time else "не указано"
                media_text = " (нужен отчёт)" if task_type.requires_media else ""

                lines.append(
                    f"📋 **{task_type.name}**\n"
                    f"   ⏱ {exec_time}{media_text}"
                )

                # Кнопки для каждой карточки
                buttons.append([
                    InlineKeyboardButton(
                        text=f"✅ Выбрать {task_type.name}",
                        callback_data=f"ADMIN_TASK_TYPE_SELECT:{task_type.id}",
                    ),
                    InlineKeyboardButton(
                        text=f"🗑 Удалить {task_type.name}",
                        callback_data=f"ADMIN_TASK_TYPE_DELETE:{task_type.id}",
                    )
                ])

            text = "\n".join(lines)

            # Кнопка "Создать новую карточку"
            buttons.append([
                InlineKeyboardButton(
                    text="➕ Создать новую карточку",
                    callback_data="ADMIN_ADD_TASK_TYPE",
                )
            ])

            # Кнопка "Назад"
            buttons.append([
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_TASK_TYPE_SELECT:"))
async def handle_task_type_select(callback: CallbackQuery):
    """Показ подробной информации о выбранной карточке"""
    task_type_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        task_type = await session.get(TaskType, task_type_id)

        if not task_type or not task_type.is_active:
            await callback.answer("Карточка не найдена", show_alert=True)
            return

        exec_time = f"{task_type.execution_time} мин" if task_type.execution_time else "не указано"
        media_text = "требуется" if task_type.requires_media else "не требуется"

        text = (
            f"📋 **Карточка задания: {task_type.name}**\n\n"
            f"📝 **Описание:** {task_type.description}\n"
            f"⏱ **Время выполнения:** {exec_time}\n"
            f"📸 **Отчёт:** {media_text}\n"
            f"🆔 **ID:** {task_type.id}\n\n"
            f"Что вы хотите сделать с этой карточкой?"
        )

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [
            [
                InlineKeyboardButton(
                    text="🚀 Назначить ребёнку",
                    callback_data=f"ADMIN_TASK_TYPE_ASSIGN:{task_type.id}",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ К списку", callback_data="ADMIN_TASK_TYPE_LIST")
            ]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_TASK_TYPE_ASSIGN:"))
async def handle_task_type_assign(callback: CallbackQuery):
    """Назначение выбранной карточки ребёнку"""
    task_type_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        task_type = await session.get(TaskType, task_type_id)

        if not task_type or not task_type.is_active:
            await callback.answer("Карточка не найдена", show_alert=True)
            return

        # Получаем активных детей
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True)
        )
        children = result.scalars().all()

        if not children:
            await callback.answer("Нет активных детей", show_alert=True)
            return

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = []
        for child in children:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👦 {child.display_name}",
                    callback_data=f"ADMIN_ASSIGN_TASK_DO:{task_type.id}:{child.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ADMIN_TASK_TYPE_SELECT:{task_type.id}")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"🚀 **Назначение задания**\n\n"
            f"📋 **{task_type.name}**\n\n"
            f"Выберите ребёнка, которому назначить это задание:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_ASSIGN_TASK_DO:"))
async def handle_assign_task_do(callback: CallbackQuery):
    """Создание задачи для ребёнка"""
    # data format: ADMIN_ASSIGN_TASK_DO:task_type_id:child_id
    parts = callback.data.split(":")
    task_type_id = int(parts[1])
    child_id = int(parts[2])

    from datetime import date
    from db.models import Task, TaskStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        child = await session.get(User, child_id)
        task_type = await session.get(TaskType, task_type_id)

        if not child or not task_type:
            await callback.answer("Ошибка: данные не найдены", show_alert=True)
            return

        # Проверяем, нет ли уже такой задачи на сегодня
        today = date.today()
        existing = await session.execute(
            select(Task).where(
                Task.child_id == child_id,
                Task.task_type_id == task_type_id,
                Task.scheduled_date == today
            )
        )
        if existing.scalar_one_or_none():
            await callback.answer("Это задание уже назначено ребёнку на сегодня!", show_alert=True)
            return

        # Получаем награду для этого ребёнка и типа задания
        reward_res = await session.execute(
            select(ChildTaskReward).where(
                ChildTaskReward.child_id == child_id,
                ChildTaskReward.task_type_id == task_type_id
            )
        )
        reward = reward_res.scalar_one_or_none()
        reward_amount = reward.reward_amount if reward else Decimal(0)

        # Создаем задачу
        task = Task(
            child_id=child_id,
            task_type_id=task_type_id,
            scheduled_date=today,
            status=TaskStatus.PENDING,
            reward_amount=reward_amount,
            currency="ARS"
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        # Отправляем уведомление ребёнку
        from bot.main import Bot
        from bot.config import BOT_TOKEN, FAMILY_CHAT_ID
        from aiogram import Bot as AiogramBot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        bot = AiogramBot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

        message_text = (
            f"🔔 **НОВОЕ ЗАДАНИЕ**\n\n"
            f"{child.display_name}, тебе назначено задание:\n"
            f"📋 **{task_type.name}**\n"
            f"💰 Награда: {reward_amount} ARS\n\n"
            f"Нужно выполнить сегодня!"
        )

        from bot.keyboards.inline import get_task_completion_keyboard
        keyboard = get_task_completion_keyboard(task.id)

        chat_id = FAMILY_CHAT_ID if FAMILY_CHAT_ID else child.telegram_user_id

        try:
            if chat_id:
                await bot.send_message(chat_id=chat_id, text=message_text, reply_markup=keyboard)
                await callback.answer("✅ Задание отправлено!", show_alert=True)
                await callback.message.edit_text(
                    f"✅ **Задание успешно назначено и отправлено!**\n\n"
                    f"👦 Ребёнок: {child.display_name}\n"
                    f"📋 Задание: {task_type.name}\n"
                    f"📅 Дата: {today}\n"
                    f"💰 Награда: {reward_amount} ARS",
                    reply_markup=get_back_button_menu()
                )
            else:
                await callback.answer("⚠️ Задача создана, но некуда отправить уведомление", show_alert=True)
        except Exception as e:
            logger.error(f"Failed to send manual task: {e}")
            await callback.answer("⚠️ Задача создана, но ошибка отправки", show_alert=True)
        finally:
            await bot.session.close()


@router.callback_query(lambda c: c.data.startswith("ADMIN_TASK_TYPE_DELETE:"))
async def handle_task_type_delete(callback: CallbackQuery):
    """Удаление типа задания"""
    task_type_id = int(callback.data.split(":")[1])
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TaskType).where(TaskType.id == task_type_id)
        )
        task_type = result.scalar_one_or_none()

        if not task_type:
            await callback.answer("Тип задания не найден", show_alert=True)
            return

        task_name = task_type.name
        # Мягкое удаление - помечаем как неактивного
        task_type.is_active = False
        await session.commit()

    await callback.answer(f"Тип задания '{task_name}' удалён (деактивирован)", show_alert=True)

    # Обновляем список
    await handle_task_type_list(callback)

