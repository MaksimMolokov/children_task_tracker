"""
Команды администратора.
См. SPEC.md раздел 4.2 "Управление типами заданий",
раздел 4.3 "Настройка денежной ставки",
раздел 4.4 "Настройка расписания"
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import ADMIN_TELEGRAM_ID
from bot.middleware.auth import AdminMiddleware

router = Router()

# Применяем middleware для проверки прав админа ко всем обработчикам
router.message.middleware(AdminMiddleware())


@router.message(Command("add_child"))
async def cmd_add_child(message: Message):
    """
    Команда /add_child
    См. SPEC.md раздел 4.1:
    - Бот спрашивает: "Как зовут ребёнка?"
    - Затем просит переслать/ответить на сообщение от ребёнка
    - Создаёт запись в users с ролью child
    """
    # TODO: Реализовать диалог для добавления ребёнка
    await message.answer(
        "Добавление ребёнка.\n"
        "Как зовут ребёнка? (Отправьте имя)"
    )


@router.message(Command("add_task_type"))
async def cmd_add_task_type(message: Message):
    """
    Команда /add_task_type
    См. SPEC.md раздел 4.2:
    - Диалог: название, описание, категория, требуется ли медиа
    - Создаёт запись в task_types
    """
    # TODO: Реализовать диалог для добавления типа задания
    await message.answer(
        "Добавление типа задания.\n"
        "Введите название задания:"
    )


@router.message(Command("list_task_types"))
async def cmd_list_task_types(message: Message):
    """
    Команда /list_task_types
    См. SPEC.md раздел 4.2:
    - Показывает список активных шаблонов с ID-названиями
    """
    # TODO: Реализовать вывод списка типов заданий
    await message.answer("Список типов заданий:\n(реализация в процессе)")


@router.message(Command("disable_task_type"))
async def cmd_disable_task_type(message: Message):
    """
    Команда /disable_task_type <id>
    См. SPEC.md раздел 4.2:
    - Помечает is_active = false для указанного типа задания
    """
    # TODO: Реализовать отключение типа задания
    await message.answer("Отключение типа задания.\nИспользование: /disable_task_type <id>")


@router.message(Command("set_reward"))
async def cmd_set_reward(message: Message):
    """
    Команда /set_reward
    См. SPEC.md раздел 4.3:
    - Диалог: выбор ребёнка, выбор задания, ввод суммы
    - Создаёт/обновляет запись в child_task_rewards
    """
    # TODO: Реализовать диалог для настройки ставки
    await message.answer(
        "Настройка денежной ставки.\n"
        "Выберите ребёнка:"
    )


@router.message(Command("list_rewards"))
async def cmd_list_rewards(message: Message):
    """
    Команда /list_rewards [child_name]
    См. SPEC.md раздел 4.3:
    - Показывает все пары "задание → ставка" для ребёнка
    """
    # TODO: Реализовать вывод списка ставок
    await message.answer("Список ставок:\n(реализация в процессе)")


@router.message(Command("add_schedule"))
async def cmd_add_schedule(message: Message):
    """
    Команда /add_schedule
    См. SPEC.md раздел 4.4:
    - Диалог: выбор TaskType, выбор детей, периодичность, время
    - Создаёт запись в schedules
    """
    # TODO: Реализовать диалог для добавления расписания
    await message.answer(
        "Добавление расписания.\n"
        "Выберите тип задания:"
    )


@router.message(Command("list_schedules"))
async def cmd_list_schedules(message: Message):
    """
    Команда /list_schedules
    См. SPEC.md раздел 4.4:
    - Показывает все активные расписания
    """
    # TODO: Реализовать вывод списка расписаний
    await message.answer("Список расписаний:\n(реализация в процессе)")


@router.message(Command("disable_schedule"))
async def cmd_disable_schedule(message: Message):
    """
    Команда /disable_schedule <id>
    См. SPEC.md раздел 4.4:
    - Помечает is_active = false для указанного расписания
    """
    # TODO: Реализовать отключение расписания
    await message.answer("Отключение расписания.\nИспользование: /disable_schedule <id>")

