"""
Обработчики для управления детьми.
"""
import logging

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, delete

from bot.keyboards.admin import get_admin_children_menu
from db.database import AsyncSessionLocal
from db.models import User, UserRole, Task, TaskMedia, ChildTaskReward, TaskStatus
from sqlalchemy.orm import selectinload
from datetime import date, timedelta

from bot.keyboards.admin import ADMIN_BACK_MAIN

router = Router()
logger = logging.getLogger(__name__)

# Применяем middleware для проверки прав админа
from bot.middleware.auth import AdminMiddleware
from bot.middleware.auto_delete import AutoDeleteMiddleware

router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())
router.message.middleware(AutoDeleteMiddleware())




@router.callback_query(lambda c: c.data == "ADMIN_CHILD_LIST")
async def handle_child_list(callback: CallbackQuery):
    """Список всех детей с кнопками удаления"""
    await callback.answer()
    from sqlalchemy import select
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.CHILD, User.is_active == True).order_by(User.created_at.desc())
        )
        children = result.scalars().all()

        if not children:
            text = (
                "👦 Список детей\n\n"
                "Дети ещё не добавлены.\n\n"
                "💡 Подсказка: Для добавления детей используйте раздел:\n"
                "🔐 Доступы → ➕ Добавить пользователя → выберите роль 'Пользователь'"
            )
            keyboard = get_admin_children_menu()
        else:
            lines = ["👦 Список детей\n"]
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
                    f"👦 {child.display_name}{age_text} — {status}{telegram_info}"
                )
                # Кнопки «Задания» и «Удалить» для каждого ребёнка
                buttons.append([
                    InlineKeyboardButton(
                        text=f"📋 Задания",
                        callback_data=f"ADMIN_CHILD_TASKS:{child.id}",
                    ),
                    InlineKeyboardButton(
                        text=f"🗑 Удалить",
                        callback_data=f"ADMIN_CHILD_DELETE:{child.id}",
                    ),
                ])

            text = "\n".join(lines)
            
            # Кнопка для добавления через "Доступы"
            buttons.append([
                InlineKeyboardButton(
                    text="➕ Добавить ребёнка (через Доступы)",
                    callback_data="ADMIN_ACCESS",
                )
            ])
            
            # Кнопка "Назад"
            buttons.append([
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_CHILDREN"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("ADMIN_CHILD_TASKS:"))
async def handle_child_tasks(callback: CallbackQuery):
    """Просмотр назначенных заданий для выбранного ребёнка."""
    child_id = int(callback.data.split(":")[1])
    await callback.answer()
    async with AsyncSessionLocal() as session:
        child = await session.get(User, child_id)
        if not child or child.role != UserRole.CHILD:
            await callback.message.edit_text(
                "Ребёнок не найден.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ К списку детей", callback_data="ADMIN_CHILD_LIST")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)],
                ]),
            )
            return
        # Задания на сегодня и за последние 7 дней
        today = date.today()
        week_ago = today - timedelta(days=7)
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.task_type))
            .where(Task.child_id == child_id, Task.scheduled_date >= week_ago)
            .order_by(Task.scheduled_date.desc())
        )
        tasks = result.scalars().all()
    child_name = child.display_name or f"Ребёнок {child_id}"
    status_emoji = {
        TaskStatus.DONE: "✅",
        TaskStatus.FAILED: "❌",
        TaskStatus.EXPIRED: "⏰",
        TaskStatus.PENDING: "⏳",
    }
    if not tasks:
        text = f"📋 Задания — {child_name}\n\nНет назначенных заданий за последние 7 дней."
    else:
        lines = [f"📋 Задания — {child_name}\n"]
        for task in tasks:
            emoji = status_emoji.get(task.status, "❓")
            lines.append(f"• {task.scheduled_date} — {task.task_type.name} — {emoji}")
        text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К списку детей", callback_data="ADMIN_CHILD_LIST")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN)],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)


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

