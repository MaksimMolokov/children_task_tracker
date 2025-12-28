"""
Обработчики для управления типами заданий.
"""
import logging

from aiogram import Router
from aiogram.types import CallbackQuery

from bot.keyboards.admin import get_admin_rewards_menu, get_back_button_menu
from bot.middleware.auth import AdminMiddleware
from db.database import AsyncSessionLocal
from db.models import Schedule, SchedulePeriodicity, TaskType, User, UserRole, ChildTaskReward
from sqlalchemy import select
from decimal import Decimal

# Константы для дней недели (для отображения расписания)
DAYS_OF_WEEK = {
    "MON": "Понедельник",
    "TUE": "Вторник",
    "WED": "Среда",
    "THU": "Четверг",
    "FRI": "Пятница",
    "SAT": "Суббота",
    "SUN": "Воскресенье",
}

router = Router()
logger = logging.getLogger(__name__)

router.callback_query.middleware(AdminMiddleware())


@router.callback_query(lambda c: c.data == "ADMIN_ASSIGN_TASK_LIST")
async def handle_assign_task_list(callback: CallbackQuery):
    """Список карточек для назначения задания"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TaskType).where(TaskType.is_active == True).order_by(TaskType.created_at.desc())
        )
        task_types = result.scalars().all()

        if not task_types:
            text = "📋 Назначить задание\n\n" "Карточки заданий ещё не созданы."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_BACK_MAIN"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
                ]
            ])
        else:
            lines = ["📋 Назначить задание\n\n" "Выберите карточку задания:"]
            buttons = []

            for task_type in task_types:
                exec_time = f"{task_type.execution_time} мин" if task_type.execution_time else "не указано"
                media_text = " (нужен отчёт)" if task_type.requires_media else ""

                lines.append(
                    f"📋 {task_type.name}\n"
                    f"   ⏱ {exec_time}{media_text}"
                )

                buttons.append([
                    InlineKeyboardButton(
                        text=f"✅ Выбрать {task_type.name}",
                        callback_data=f"ADMIN_ASSIGN_TASK_SELECT:{task_type.id}",
                    )
                ])

            text = "\n".join(lines)

            buttons.append([
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_BACK_MAIN"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_ASSIGN_TASK_SELECT:"))
async def handle_assign_task_select(callback: CallbackQuery):
    """Показ summary карточки перед назначением"""
    task_type_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        task_type = await session.get(TaskType, task_type_id)

        if not task_type or not task_type.is_active:
            await callback.answer("Карточка не найдена", show_alert=True)
            return

        # Получаем расписание для этой карточки
        schedule_result = await session.execute(
            select(Schedule).where(
                Schedule.task_type_id == task_type_id,
                Schedule.is_active == True
            )
        )
        schedule = schedule_result.scalar_one_or_none()

        exec_time = f"{task_type.execution_time} мин" if task_type.execution_time else "не указано"
        media_text = "требуется" if task_type.requires_media else "не требуется"

        # Формируем информацию о расписании
        schedule_text = "не указано"
        if schedule:
            days_of_week = schedule.days_of_week
            if schedule.periodicity == SchedulePeriodicity.DAILY:
                if days_of_week == "MON,TUE,WED,THU,FRI,SAT,SUN":
                    schedule_text = "Каждый день"
                elif days_of_week == "MON,TUE,WED,THU,FRI":
                    schedule_text = "Будни (Пн-Пт)"
                elif days_of_week == "SAT,SUN":
                    schedule_text = "Выходные (Сб-Вс)"
                else:
                    days_list = days_of_week.split(",")
                    days_names = [DAYS_OF_WEEK.get(day, day) for day in days_list]
                    schedule_text = ", ".join(days_names)
            elif schedule.periodicity == SchedulePeriodicity.WEEKLY:
                day_name = DAYS_OF_WEEK.get(days_of_week, days_of_week)
                schedule_text = f"Раз в неделю ({day_name})"
            
            time_str = schedule.time_of_day.strftime("%H:%M") if schedule.time_of_day else "не указано"
            schedule_text = f"{schedule_text}, время: {time_str}"

        reward_text = f"{task_type.reward_amount} ARS" if task_type.reward_amount else "не указано"

        text = (
            f"📋 Карточка задания: {task_type.name}\n\n"
            f"📝 Описание: {task_type.description or 'не указано'}\n"
            f"⏱ Время выполнения: {exec_time}\n"
            f"💰 Стоимость (базовая): {reward_text}\n"
            f"📸 Отчёт: {media_text}\n"
            f"🗓 Расписание: {schedule_text}\n\n"
            f"Продолжить назначение этого задания?"
        )

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [
            [
                InlineKeyboardButton(text="✅ ОК", callback_data=f"ADMIN_ASSIGN_TASK_OK:{task_type_id}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_ASSIGN_TASK_LIST"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
            ]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_ASSIGN_TASK_OK:"))
async def handle_assign_task_ok(callback: CallbackQuery):
    """После подтверждения summary показываем список детей"""
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
                    callback_data=f"ADMIN_ASSIGN_TASK_CHILD:{task_type_id}:{child.id}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ADMIN_ASSIGN_TASK_SELECT:{task_type_id}"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"🚀 Назначение задания\n\n"
            f"📋 {task_type.name}\n\n"
            f"Выберите ребёнка, которому назначить это задание:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("ADMIN_ASSIGN_TASK_CHILD:"))
async def handle_assign_task_child_selected(callback: CallbackQuery):
    """Ребенок выбран, показываем подтверждение"""
    parts = callback.data.split(":")
    task_type_id = int(parts[1])
    child_id = int(parts[2])

    async with AsyncSessionLocal() as session:
        child = await session.get(User, child_id)
        task_type = await session.get(TaskType, task_type_id)

        if not child or not task_type:
            await callback.answer("Ошибка: данные не найдены", show_alert=True)
            return

        text = (
            f"Подтверждаете назначение карточки \"{task_type.name}\" для \"{child.display_name}\"?"
        )

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Да, назначить",
                    callback_data=f"ADMIN_ASSIGN_TASK_DO:{task_type_id}:{child_id}",
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ADMIN_ASSIGN_TASK_OK:{task_type_id}"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
            ]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()


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
            text = "📋 Список карточек заданий\n\n" "Карточки ещё не созданы."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Создать новую карточку",
                        callback_data="ADMIN_ADD_TASK_TYPE",
                    )
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
                ]
            ])
        else:
            lines = ["📋 Список карточек заданий\n"]
            buttons = []

            for task_type in task_types:
                exec_time = f"{task_type.execution_time} мин" if task_type.execution_time else "не указано"
                media_text = " (нужен отчёт)" if task_type.requires_media else ""

                lines.append(
                    f"📋 {task_type.name}\n"
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
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REWARDS"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
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
            f"📋 Карточка задания: {task_type.name}\n\n"
            f"📝 Описание: {task_type.description}\n"
            f"⏱ Время выполнения: {exec_time}\n"
            f"📸 Отчёт: {media_text}\n"
            f"🆔 ID: {task_type.id}"
        )

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [
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
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ADMIN_TASK_TYPE_SELECT:{task_type.id}"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="ADMIN_BACK_MAIN")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"🚀 Назначение задания\n\n"
            f"📋 {task_type.name}\n\n"
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

        # Получаем награду для этого ребёнка и типа задания (или дефолтную)
        reward_res = await session.execute(
            select(ChildTaskReward).where(
                ChildTaskReward.child_id == child_id,
                ChildTaskReward.task_type_id == task_type_id
            )
        )
        reward = reward_res.scalar_one_or_none()
        reward_amount = reward.reward_amount if reward else (task_type.reward_amount or Decimal(0))

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
        
        # Логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Task created: id={task.id}, child_id={child_id}, task_type_id={task_type_id}, "
            f"scheduled_date={task.scheduled_date}, status={task.status}, reward_amount={task.reward_amount}"
        )

        # Формируем сообщение для администратора
        success_message = f"Для ребенка \"{child.display_name}\" назначено задание \"{task_type.name}\""

        # Отправляем уведомление ребёнку
        from bot.main import Bot
        from bot.config import BOT_TOKEN, FAMILY_CHAT_ID
        from aiogram import Bot as AiogramBot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        bot = AiogramBot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

        # Получаем расписание для этой карточки
        schedule_res = await session.execute(
            select(Schedule).where(
                Schedule.task_type_id == task_type_id,
                Schedule.is_active == True
            )
        )
        schedule = schedule_res.scalar_one_or_none()

        # Формируем информацию о расписании для уведомления
        schedule_info = ""
        if schedule:
            days_of_week = schedule.days_of_week
            if schedule.periodicity == SchedulePeriodicity.DAILY:
                if days_of_week == "MON,TUE,WED,THU,FRI,SAT,SUN":
                    schedule_days = "Каждый день"
                elif days_of_week == "MON,TUE,WED,THU,FRI":
                    schedule_days = "Будни (Пн-Пт)"
                elif days_of_week == "SAT,SUN":
                    schedule_days = "Выходные (Сб-Вс)"
                else:
                    days_list = days_of_week.split(",")
                    days_names = [DAYS_OF_WEEK.get(day, day) for day in days_list]
                    schedule_days = ", ".join(days_names)
            elif schedule.periodicity == SchedulePeriodicity.WEEKLY:
                day_name = DAYS_OF_WEEK.get(days_of_week, days_of_week)
                schedule_days = f"Раз в неделю ({day_name})"
            else:
                schedule_days = "не указано"
            
            time_str = schedule.time_of_day.strftime("%H:%M") if schedule.time_of_day else "не указано"
            schedule_info = f"\n🗓 Расписание: {schedule_days}, время: {time_str}"

        # Формируем информацию об отчете
        report_info = ""
        if task_type.requires_media:
            report_info = "\n📸 Требуется отчет: При выполнении задания нужно приложить фото или видео"
        
        message_text = (
            f"🔔 НОВОЕ ЗАДАНИЕ\n\n"
            f"{child.display_name}, тебе назначено задание:\n"
            f"📋 {task_type.name}\n"
            f"📝 {task_type.description or ''}{report_info}\n"
            f"⏱ Время выполнения: {task_type.execution_time or 'не указано'} минут\n"
            f"💰 Награда: {reward_amount} ARS{schedule_info}\n\n"
            f"Нужно выполнить сегодня!"
        )

        from bot.keyboards.inline import get_task_completion_keyboard
        keyboard = get_task_completion_keyboard()

        chat_id = FAMILY_CHAT_ID if FAMILY_CHAT_ID else child.telegram_user_id

        try:
            if chat_id:
                sent_message = await bot.send_message(chat_id=chat_id, text=message_text, reply_markup=keyboard)
                # Сохраняем message_id и chat_id в задание
                task.message_id = sent_message.message_id
                task.chat_id = chat_id
                await session.commit()
                await session.refresh(task)
                logger.info(f"Task assigned: task_id={task.id}, message_id={sent_message.message_id}, chat_id={chat_id}")
                await callback.answer("✅ Задание отправлено!", show_alert=True)
                await callback.message.edit_text(
                    success_message,
                    reply_markup=get_back_button_menu()
                )
            else:
                await callback.answer("⚠️ Задача создана, но некуда отправить уведомление", show_alert=True)
                await callback.message.edit_text(
                    success_message,
                    reply_markup=get_back_button_menu()
                )
        except Exception as e:
            logger.error(f"Failed to send manual task: {e}")
            await callback.answer("⚠️ Задача создана, но ошибка отправки", show_alert=True)
            await callback.message.edit_text(
                success_message,
                reply_markup=get_back_button_menu()
            )
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

