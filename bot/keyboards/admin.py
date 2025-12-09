"""
Inline-клавиатуры для админ-меню.
См. SPEC.md раздел 7 "Админ-меню и кнопки бота"
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Префиксы callback для админ-меню
ADMIN_CHECK_TASKS = "ADMIN_CHECK_TASKS"
ADMIN_ASSIGN_TASK = "ADMIN_ASSIGN_TASK"
ADMIN_SCHEDULES = "ADMIN_SCHEDULES"
ADMIN_CHILDREN = "ADMIN_CHILDREN"
ADMIN_REWARDS = "ADMIN_REWARDS"
ADMIN_REPORTS = "ADMIN_REPORTS"
ADMIN_LEADERS = "ADMIN_LEADERS"
ADMIN_TESTING = "ADMIN_TESTING"
ADMIN_BACK_MAIN = "ADMIN_BACK_MAIN"


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """
    Главное админ-меню.
    См. SPEC.md раздел 7.1
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Проверка заданий", callback_data=ADMIN_CHECK_TASKS),
                InlineKeyboardButton(text="➕ Назначить задание", callback_data=ADMIN_ASSIGN_TASK),
            ],
            [
                InlineKeyboardButton(text="🗓 Расписания", callback_data=ADMIN_SCHEDULES),
                InlineKeyboardButton(text="👦 Дети", callback_data=ADMIN_CHILDREN),
            ],
            [
                InlineKeyboardButton(text="💰 Ставки", callback_data=ADMIN_REWARDS),
                InlineKeyboardButton(text="📊 Отчёты", callback_data=ADMIN_REPORTS),
            ],
            [
                InlineKeyboardButton(text="🏆 Лидеры", callback_data=ADMIN_LEADERS),
            ],
            [
                InlineKeyboardButton(text="🧪 Тестирование", callback_data=ADMIN_TESTING),
            ],
        ]
    )
    return keyboard


def get_admin_check_tasks_menu() -> InlineKeyboardMarkup:
    """
    Меню проверки заданий.
    См. SPEC.md раздел 7.2
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Сегодня по детям",
                    callback_data="ADMIN_CHECK_TODAY_BY_CHILD",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👦 По ребёнку",
                    callback_data="ADMIN_CHECK_BY_CHILD_SELECT",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔍 Требуют проверки",
                    callback_data="ADMIN_CHECK_NEED_REVIEW",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Просроченные / не сделаны",
                    callback_data="ADMIN_CHECK_FAILED_TODAY",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_schedules_menu() -> InlineKeyboardMarkup:
    """
    Меню расписаний.
    См. SPEC.md раздел 7.4
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Новое расписание",
                    callback_data="ADMIN_SCHEDULE_ADD",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📃 Список расписаний",
                    callback_data="ADMIN_SCHEDULE_LIST",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_children_menu() -> InlineKeyboardMarkup:
    """
    Меню управления детьми.
    См. SPEC.md раздел 7.5
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить ребёнка",
                    callback_data="ADMIN_CHILD_ADD",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📃 Список детей",
                    callback_data="ADMIN_CHILD_LIST",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список типов заданий",
                    callback_data="ADMIN_TASK_TYPE_LIST",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_rewards_menu() -> InlineKeyboardMarkup:
    """
    Меню ставок.
    См. SPEC.md раздел 7.6
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👦 По ребёнку",
                    callback_data="ADMIN_REWARDS_BY_CHILD_SELECT",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 По заданию",
                    callback_data="ADMIN_REWARDS_BY_TASKTYPE_SELECT",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Создать тип задания",
                    callback_data="ADMIN_ADD_TASK_TYPE",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_reports_menu() -> InlineKeyboardMarkup:
    """
    Меню отчётов.
    См. SPEC.md раздел 7.7
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Отчёт за сегодня",
                    callback_data="ADMIN_REPORT_TODAY",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 Отчёт за вчера",
                    callback_data="ADMIN_REPORT_YESTERDAY",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Еженедельный отчёт",
                    callback_data="ADMIN_REPORT_WEEK",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_leaders_menu() -> InlineKeyboardMarkup:
    """
    Меню лидеров.
    См. SPEC.md раздел 7.8
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 За неделю",
                    callback_data="ADMIN_LEADERS_WEEK",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 За месяц",
                    callback_data="ADMIN_LEADERS_MONTH",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_back_button_menu() -> InlineKeyboardMarkup:
    """Простая кнопка "Назад" в главное меню"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard

