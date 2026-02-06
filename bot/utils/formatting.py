"""
Общие утилиты форматирования (дни недели, периоды).
"""
from datetime import date, timedelta

WEEKDAYS_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


def get_week_days_string(week_start: date, week_end: date) -> str:
    """Получить строку с днями недели для периода."""
    days = []
    current = week_start
    while current <= week_end:
        days.append(WEEKDAYS_RU[current.weekday()])
        current += timedelta(days=1)
    return ", ".join(days)
