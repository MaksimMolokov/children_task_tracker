"""
Inline-кнопки для бота.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import TASK_COMPLETE


def get_task_completion_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка "✅ Выполнил" для подтверждения выполнения задания.
    См. SPEC.md раздел 5.1 - inline-кнопка с callback "task_complete"
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнил", callback_data=TASK_COMPLETE)]
        ]
    )
    return keyboard



