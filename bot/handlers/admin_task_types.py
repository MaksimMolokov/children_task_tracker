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
            text = "📋 **Список типов заданий**\n\n" "Типы заданий ещё не созданы."
            keyboard = get_back_button_menu()
        else:
            lines = ["📋 **Список типов заданий**\n"]
            buttons = []

            for task_type in task_types:
                status = "✅ active" if task_type.is_active else "❌ inactive"
                description_text = f"\n   {task_type.description[:50]}..." if task_type.description else ""
                exec_time = f", {task_type.execution_time} мин" if task_type.execution_time else ""
                media_text = ", нужен отчёт" if task_type.requires_media else ""
                
                lines.append(
                    f"📋 **{task_type.name}** ({task_type.category.value}){exec_time}{media_text} — {status}{description_text}"
                )
                # Кнопка удаления для каждого задания
                buttons.append([
                    InlineKeyboardButton(
                        text=f"🗑 Удалить {task_type.name}",
                        callback_data=f"ADMIN_TASK_TYPE_DELETE:{task_type.id}",
                    )
                ])

            text = "\n".join(lines)

            # Кнопка "Добавить задание"
            buttons.append([
                InlineKeyboardButton(
                    text="➕ Создать тип задания",
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

