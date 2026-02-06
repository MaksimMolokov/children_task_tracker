"""
Inline-клавиатуры для админ-меню.
См. SPEC.md раздел 7 "Админ-меню и кнопки бота"
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

# Префиксы callback для админ-меню
ADMIN_CHECK_TASKS = "ADMIN_CHECK_TASKS"
ADMIN_ASSIGN_TASK = "ADMIN_ASSIGN_TASK"
ADMIN_SCHEDULES = "ADMIN_SCHEDULES"
ADMIN_CHILDREN = "ADMIN_CHILDREN"
ADMIN_REWARDS = "ADMIN_REWARDS"
ADMIN_REPORTS = "ADMIN_REPORTS"
ADMIN_LEADERS = "ADMIN_LEADERS"
ADMIN_TESTING = "ADMIN_TESTING"
ADMIN_ACCESS = "ADMIN_ACCESS"
ADMIN_LOGS = "ADMIN_LOGS"
ADMIN_BACK_MAIN = "ADMIN_BACK_MAIN"

# Тексты кнопок нижней клавиатуры (ReplyKeyboard) — должны совпадать с обработчиками
REPLY_CHECK_TASKS = "📋 Проверка заданий"
REPLY_ASSIGN_TASK = "➕ Назначить задание"
REPLY_CHILDREN = "👦 Дети"
REPLY_REWARDS = "🗂 Карточки заданий"
REPLY_REPORTS = "📊 Отчёты"
REPLY_ACCESS = "🔐 Доступы"
REPLY_LEADERS = "🏆 Лидеры"
REPLY_TESTING = "🧪 Тестирование"
REPLY_LOGS = "📜 Логи"
REPLY_FAQ = "❓ FAQ"
REPLY_FEEDBACK = "💬 Обратная связь"


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Постоянная клавиатура внизу чата для админа (кнопки всегда видны).
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=REPLY_CHECK_TASKS), KeyboardButton(text=REPLY_ASSIGN_TASK)],
            [KeyboardButton(text=REPLY_CHILDREN), KeyboardButton(text=REPLY_REWARDS)],
            [KeyboardButton(text=REPLY_ACCESS), KeyboardButton(text=REPLY_REPORTS)],
            [KeyboardButton(text=REPLY_FAQ), KeyboardButton(text=REPLY_FEEDBACK)],
            [KeyboardButton(text=REPLY_LEADERS)],
            [KeyboardButton(text=REPLY_TESTING), KeyboardButton(text=REPLY_LOGS)],
        ],
        resize_keyboard=True,
    )
    return keyboard


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
                InlineKeyboardButton(text="👦 Дети", callback_data=ADMIN_CHILDREN),
            ],
            [
                InlineKeyboardButton(text="🗂 Карточки заданий", callback_data=ADMIN_REWARDS),
                InlineKeyboardButton(text="📊 Отчёты", callback_data=ADMIN_REPORTS),
            ],
            [
                InlineKeyboardButton(text="🔐 Доступы", callback_data=ADMIN_ACCESS),
            ],
            [
                InlineKeyboardButton(text="🏆 Лидеры", callback_data=ADMIN_LEADERS),
            ],
            [
                InlineKeyboardButton(text="🧪 Тестирование", callback_data=ADMIN_TESTING),
            ],
            [
                InlineKeyboardButton(text="📜 Логи", callback_data=ADMIN_LOGS),
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
                    text="📅 Задания на сегодня (✅/❌)",
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
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
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
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_rewards_menu() -> InlineKeyboardMarkup:
    """
    Меню карточек заданий.
    См. SPEC.md раздел 7.6
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Список карточек",
                    callback_data="ADMIN_TASK_TYPE_LIST",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Создать новую карточку",
                    callback_data="ADMIN_ADD_TASK_TYPE",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_reports_menu() -> InlineKeyboardMarkup:
    """
    Меню отчётов - выбор периода.
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Вчера",
                    callback_data="ADMIN_REPORT_PERIOD_YESTERDAY",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 Сегодня",
                    callback_data="ADMIN_REPORT_PERIOD_TODAY",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 За неделю",
                    callback_data="ADMIN_REPORT_PERIOD_WEEK",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_report_type_menu(period: str) -> InlineKeyboardMarkup:
    """
    Меню выбора типа отчета после выбора периода.
    period: "yesterday", "today", "week"
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Итого",
                    callback_data=f"ADMIN_REPORT_TOTAL:{period}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👦 По детям",
                    callback_data=f"ADMIN_REPORT_BY_CHILD:{period}",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ADMIN_REPORTS"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
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
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_admin_access_menu() -> InlineKeyboardMarkup:
    """
    Меню управления доступами.
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить пользователя",
                    callback_data="ADMIN_USER_ADD",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📃 Список пользователей",
                    callback_data="ADMIN_ACCESS_LIST",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=ADMIN_BACK_MAIN),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard


def get_back_button_menu(back_callback: str = None) -> InlineKeyboardMarkup:
    """
    Кнопки "Назад" и "Главное меню".
    Если back_callback не указан, "Назад" ведет в главное меню.
    """
    if back_callback is None:
        back_callback = ADMIN_BACK_MAIN
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data=ADMIN_BACK_MAIN),
            ],
        ]
    )
    return keyboard

