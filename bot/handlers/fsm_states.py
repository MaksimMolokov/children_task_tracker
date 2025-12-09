"""
Состояния FSM для диалогов с администратором.
"""
from aiogram.fsm.state import State, StatesGroup


class AddChildStates(StatesGroup):
    """Состояния для добавления ребёнка"""
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_telegram_id = State()  # Опционально, можно добавить позже


class AddTaskTypeStates(StatesGroup):
    """Состояния для добавления типа задания"""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_execution_time = State()
    waiting_for_requires_media = State()
    waiting_for_frequency = State()


class SetRewardStates(StatesGroup):
    """Состояния для установки ставки"""
    waiting_for_child = State()
    waiting_for_task_type = State()
    waiting_for_amount = State()


class AddScheduleStates(StatesGroup):
    """Состояния для добавления расписания"""
    waiting_for_task_type = State()
    waiting_for_target_scope = State()
    waiting_for_children = State()
    waiting_for_periodicity = State()
    waiting_for_days_of_week = State()
    waiting_for_time = State()


