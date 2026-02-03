"""
Журнал событий для админа: запись в формате дата\tописание (по-русски).
Используется для вывода «Логи» в две колонки.
"""
import os
from datetime import datetime

from bot.config import EVENT_LOG_FILE, LOG_DIR


def log_event(description_ru: str) -> None:
    """
    Пишет в файл событий строку: YYYY-MM-DD HH:MM:SS\t{description_ru}.
    Создаёт директорию logs при необходимости.
    """
    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp}\t{description_ru}\n"
    try:
        with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass  # не падаем при ошибке записи
