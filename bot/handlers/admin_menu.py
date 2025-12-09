"""
Обработчики админ-меню через inline-кнопки.
См. SPEC.md раздел 7 "Админ-меню и кнопки бота"
"""
import logging
from datetime import date, datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import ADMIN_TELEGRAM_ID
from bot.keyboards.admin import (
    get_admin_children_menu,
    get_admin_check_tasks_menu,
    get_admin_leaders_menu,
    get_admin_main_menu,
    get_admin_reports_menu,
    get_admin_rewards_menu,
    get_admin_schedules_menu,
    get_back_button_menu,
    ADMIN_BACK_MAIN,
)
from bot.middleware.auth import AdminMiddleware

router = Router()
router.callback_query.middleware(AdminMiddleware())
router.message.middleware(AdminMiddleware())

logger = logging.getLogger(__name__)


def format_admin_guide() -> str:
    """
    Форматирование гайда для администратора.
    См. SPEC.md раздел 7.9
    """
    return (
        "📖 **Гайд по работе с ботом**\n\n"
        "**1. Добавление бота в чат**\n\n"
        "Для того, чтобы бот мог выдавать задания детям:\n"
        "1. Добавьте бота в групповой чат (или семейный чат)\n"
        "2. Сделайте бота администратором чата\n"
        "3. Детям нужно будет начать диалог с ботом (отправить /start) для регистрации\n\n"
        "**2. Как выдаются задания**\n\n"
        "Задания могут выдаваться двумя способами:\n\n"
        "**А) Автоматически по расписанию:**\n"
        "– Зайдите в меню 🗓 Расписания → ➕ Новое расписание\n"
        "– Выберите тип задания, время, дни недели и детей\n"
        "– Бот будет автоматически создавать задания и отправлять их в чат\n\n"
        "**Б) Вручную через админ-меню:**\n"
        "– Зайдите в ➕ Назначить задание\n"
        "– Выберите ребёнка, тип задания и дату\n"
        "– Задание будет создано и отправлено немедленно\n\n"
        "**3. Где видны задания**\n\n"
        "– Если настроен семейный чат (`FAMILY_CHAT_ID` в .env), задания отправляются туда\n"
        "– Если не настроен, задания отправляются детям в личные сообщения\n"
        "– Вы можете проверить статус всех заданий через 📋 Проверка заданий\n\n"
        "**4. Проверка выполненных заданий**\n\n"
        "– Дети нажимают кнопку \"✅ Выполнил\" на задании\n"
        "– Если требуется медиа, дети отправляют фото/видео ответом на сообщение с заданием\n"
        "– Вы можете вручную проверить и принять/отклонить задания через 📋 Проверка заданий"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """
    Команда /admin - вход в админ-меню.
    См. SPEC.md раздел 7.1
    """
    await message.answer(
        "🔧 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=get_admin_main_menu(),
    )


@router.callback_query(lambda c: c.data == ADMIN_BACK_MAIN)
async def handle_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.edit_text(
        "🔧 **Админ-панель**\n\n" "Выберите действие:",
        reply_markup=get_admin_main_menu(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_CHECK_TASKS")
async def handle_check_tasks(callback: CallbackQuery):
    """
    Обработка "📋 Проверка заданий".
    См. SPEC.md раздел 7.2
    """
    await callback.message.edit_text(
        "📋 **Проверка заданий**\n\n" "Выберите действие:",
        reply_markup=get_admin_check_tasks_menu(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_CHECK_TODAY_BY_CHILD")
async def handle_check_today_by_child(callback: CallbackQuery):
    """
    Показ заданий на сегодня по всем детям.
    См. SPEC.md раздел 7.2.1
    """
    # TODO: Реализовать получение задач за сегодня
    from db.database import AsyncSessionLocal
    from db.models import Task, TaskStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        today = date.today()
        result = await session.execute(
            select(Task).where(Task.scheduled_date == today)
        )
        tasks = result.scalars().all()

        if not tasks:
            text = f"📅 **Задания на сегодня ({today})**\n\n" "Нет заданий на сегодня."
        else:
            # Группировка по детям
            tasks_by_child = {}
            for task in tasks:
                child_name = task.child.display_name or f"Ребёнок {task.child_id}"
                if child_name not in tasks_by_child:
                    tasks_by_child[child_name] = []
                tasks_by_child[child_name].append(task)

            lines = [f"📅 **Задания на сегодня ({today})**\n"]
            for child_name, child_tasks in tasks_by_child.items():
                lines.append(f"👦 **{child_name}**")
                for task in child_tasks:
                    status_emoji = {
                        TaskStatus.DONE: "✅",
                        TaskStatus.FAILED: "❌",
                        TaskStatus.EXPIRED: "⏰",
                        TaskStatus.PENDING: "⏳",
                    }.get(task.status, "❓")
                    lines.append(f"– {task.task_type.name} — {status_emoji}")
                lines.append("")

            text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=get_admin_check_tasks_menu())
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_SCHEDULES")
async def handle_schedules(callback: CallbackQuery):
    """
    Обработка "🗓 Расписания".
    См. SPEC.md раздел 7.4
    """
    # Импортируем напрямую, чтобы избежать циклических импортов
    from bot.keyboards.admin import get_admin_schedules_menu
    await callback.message.edit_text(
        "🗓 **Расписания**\n\n" "Выберите действие:",
        reply_markup=get_admin_schedules_menu(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_CHILDREN")
async def handle_children(callback: CallbackQuery):
    """
    Обработка "👦 Дети".
    См. SPEC.md раздел 7.5
    """
    from bot.keyboards.admin import get_admin_children_menu
    await callback.message.edit_text(
        "👦 **Дети**\n\n" "Выберите действие:",
        reply_markup=get_admin_children_menu(),
    )
    await callback.answer()



@router.callback_query(lambda c: c.data == "ADMIN_REPORTS")
async def handle_reports(callback: CallbackQuery):
    """
    Обработка "📊 Отчёты".
    См. SPEC.md раздел 7.7
    """
    await callback.message.edit_text(
        "📊 **Отчёты**\n\n" "Выберите период:",
        reply_markup=get_admin_reports_menu(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_REPORT_TODAY")
async def handle_report_today(callback: CallbackQuery):
    """Отчёт за сегодня"""
    # TODO: Реализовать формирование отчёта
    from bot.services.report_service import ReportService
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        today = date.today()
        report_text = await ReportService.format_daily_report_text(session, today)

    await callback.message.answer(report_text)
    await callback.answer("Отчёт отправлен")


@router.callback_query(lambda c: c.data == "ADMIN_REPORT_YESTERDAY")
async def handle_report_yesterday(callback: CallbackQuery):
    """Отчёт за вчера"""
    from bot.services.report_service import ReportService
    from db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yesterday = date.today() - timedelta(days=1)
        report_text = await ReportService.format_daily_report_text(session, yesterday)

    await callback.message.answer(report_text)
    await callback.answer("Отчёт отправлен")


@router.callback_query(lambda c: c.data == "ADMIN_LEADERS")
async def handle_leaders(callback: CallbackQuery):
    """
    Обработка "🏆 Лидеры".
    См. SPEC.md раздел 7.8
    """
    await callback.message.edit_text(
        "🏆 **Лидеры**\n\n" "Выберите период:",
        reply_markup=get_admin_leaders_menu(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ADMIN_TESTING")
async def handle_testing(callback: CallbackQuery):
    """
    Обработка "🧪 Тестирование".
    """
    from bot.handlers.admin_testing import handle_testing_menu
    await handle_testing_menu(callback)


@router.callback_query(lambda c: c.data == "ADMIN_ASSIGN_TASK")
async def handle_assign_task(callback: CallbackQuery):
    """
    Обработка "➕ Назначить задание".
    См. SPEC.md раздел 7.3
    """
    await callback.message.edit_text(
        "➕ **Назначить задание**\n\n"
        "Эта функция будет реализована в следующих версиях.\n"
        "Пока используйте команды /add_task_type и настройте расписание.",
        reply_markup=get_back_button_menu(),
    )
    await callback.answer()


# Обработчик для добавления ребёнка (перенаправление)
@router.callback_query(lambda c: c.data == "ADMIN_CHILD_ADD")
async def handle_child_add_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик добавления ребёнка"""
    from bot.handlers.admin_children import handle_child_add_start
    await handle_child_add_start(callback, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == "ADMIN_ADD_TASK_TYPE")
async def handle_add_task_type_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик создания типа задания"""
    from bot.handlers.admin_rewards import handle_task_type_add_start
    await handle_task_type_add_start(callback, state)

@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_CHILD_SELECT")
async def handle_rewards_by_child_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора ребёнка для ставки"""
    from bot.handlers.admin_rewards import handle_rewards_by_child_select
    await handle_rewards_by_child_select(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD:"))
async def handle_reward_child_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора типа задания"""
    from bot.handlers.admin_rewards import handle_reward_child_selected
    await handle_reward_child_selected(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE:"))
async def handle_reward_task_type_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик ввода суммы"""
    from bot.handlers.admin_rewards import handle_reward_task_type_selected
    await handle_reward_task_type_selected(callback, state)

@router.callback_query(lambda c: c.data == "ADMIN_REWARDS_BY_TASKTYPE_SELECT")
async def handle_rewards_by_task_type_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора задания"""
    from bot.handlers.admin_rewards import handle_rewards_by_task_type_select
    await handle_rewards_by_task_type_select(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_TASK_TYPE_FIRST:"))
async def handle_reward_task_type_first_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик выбора ребёнка после задания"""
    from bot.handlers.admin_rewards import handle_reward_task_type_first_selected
    await handle_reward_task_type_first_selected(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_REWARD_CHILD_SECOND:"))
async def handle_reward_child_second_redirect(callback: CallbackQuery, state: FSMContext):
    """Перенаправление на обработчик ввода суммы после выбора ребёнка вторым"""
    from bot.handlers.admin_rewards import handle_reward_child_second_selected
    await handle_reward_child_second_selected(callback, state)

# Обработчики для остальных пунктов меню (заглушки)
@router.callback_query(lambda c: c.data == "ADMIN_TASK_TYPE_LIST")
async def handle_task_type_list_redirect(callback: CallbackQuery):
    """Перенаправление на обработчик списка типов заданий"""
    from bot.handlers.admin_task_types import handle_task_type_list
    await handle_task_type_list(callback)

@router.callback_query(lambda c: c.data.startswith("ADMIN_TASK_TYPE_DELETE:"))
async def handle_task_type_delete_redirect(callback: CallbackQuery):
    """Перенаправление на обработчик удаления типа задания"""
    from bot.handlers.admin_task_types import handle_task_type_delete
    await handle_task_type_delete(callback)

@router.callback_query(lambda c: c.data.startswith("ADMIN_CHILD_DELETE:"))
async def handle_child_delete_redirect(callback: CallbackQuery):
    """Перенаправление на обработчик удаления ребёнка"""
    from bot.handlers.admin_children import handle_child_delete
    await handle_child_delete(callback)

@router.callback_query(lambda c: c.data.startswith("ADMIN_SCHEDULE"))
async def handle_schedule_redirects(callback: CallbackQuery, state: FSMContext):
    """Перенаправление обработчиков расписания"""
    from bot.handlers.admin_schedules import (
        handle_schedule_add_start,
        handle_schedule_task_type_selected,
        handle_schedule_all_children,
        handle_schedule_select_children,
        handle_schedule_toggle_child,
        handle_schedule_children_done,
        handle_schedule_period_daily,
        handle_schedule_period_weekdays,
        handle_schedule_period_weekends,
        handle_schedule_period_weekly,
        handle_schedule_period_custom,
        handle_schedule_day_selected,
        handle_schedule_toggle_day,
        handle_schedule_days_done,
        handle_schedule_time_selected,
        handle_schedule_time_custom,
        handle_schedule_confirm,
        handle_schedule_list,
        handle_schedule_toggle,
    )
    
    if callback.data == "ADMIN_SCHEDULE_ADD":
        await handle_schedule_add_start(callback, state)
    elif callback.data.startswith("ADMIN_SCHEDULE_TASK_TYPE:"):
        await handle_schedule_task_type_selected(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_ALL_CHILDREN":
        await handle_schedule_all_children(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_SELECT_CHILDREN":
        await handle_schedule_select_children(callback, state)
    elif callback.data.startswith("ADMIN_SCHEDULE_TOGGLE_CHILD:"):
        await handle_schedule_toggle_child(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_CHILDREN_DONE":
        await handle_schedule_children_done(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_PERIOD_DAILY":
        await handle_schedule_period_daily(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_PERIOD_WEEKDAYS":
        await handle_schedule_period_weekdays(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_PERIOD_WEEKENDS":
        await handle_schedule_period_weekends(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_PERIOD_WEEKLY":
        await handle_schedule_period_weekly(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_PERIOD_CUSTOM":
        await handle_schedule_period_custom(callback, state)
    elif callback.data.startswith("ADMIN_SCHEDULE_DAY:"):
        await handle_schedule_day_selected(callback, state)
    elif callback.data.startswith("ADMIN_SCHEDULE_TOGGLE_DAY:"):
        await handle_schedule_toggle_day(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_DAYS_DONE":
        await handle_schedule_days_done(callback, state)
    elif callback.data.startswith("ADMIN_SCHEDULE_TIME:"):
        await handle_schedule_time_selected(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_TIME_CUSTOM":
        await handle_schedule_time_custom(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_CONFIRM":
        await handle_schedule_confirm(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_LIST":
        await handle_schedule_list(callback)
    elif callback.data.startswith("ADMIN_SCHEDULE_TOGGLE:"):
        await handle_schedule_toggle(callback)
    elif callback.data == "ADMIN_SCHEDULE_SELECT_CHILDREN_BACK":
        from bot.handlers.admin_schedules import handle_schedule_select_children_back
        await handle_schedule_select_children_back(callback, state)
    elif callback.data == "ADMIN_SCHEDULE_PERIOD_BACK":
        from bot.handlers.admin_schedules import handle_schedule_period_back
        await handle_schedule_period_back(callback, state)

@router.callback_query(lambda c: c.data.startswith("ADMIN_"))
async def handle_other_admin_callbacks(callback: CallbackQuery):
    """Заглушка для остальных админ-коллбеков"""
    # Игнорируем уже обработанные callback'и
    if callback.data in [
        "ADMIN_ADD_TASK_TYPE",
        "ADMIN_REWARD_CHILD:",
        "ADMIN_REWARD_TASK_TYPE:",
    ] or callback.data.startswith((
        "ADMIN_REWARD_CHILD:", 
        "ADMIN_REWARD_TASK_TYPE:",
        "ADMIN_TASK_TYPE_DELETE:",
        "ADMIN_CHILD_DELETE:",
        "ADMIN_REWARD_TASK_TYPE_FIRST:",
        "ADMIN_REWARD_CHILD_SECOND:",
        "ADMIN_SCHEDULE",
    )):
        return
    await callback.answer("Функция в разработке", show_alert=True)

