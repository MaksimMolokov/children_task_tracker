"""
Конфигурация приложения - чтение переменных окружения и валидация.
"""
import os
from typing import Optional

from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

# Admin Configuration
ADMIN_TELEGRAM_ID: int = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
if not ADMIN_TELEGRAM_ID:
    raise ValueError("ADMIN_TELEGRAM_ID не установлен в переменных окружения")

# Database Configuration
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/children_check"
)

# Timezone Configuration
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

# Optional: Chat IDs
FAMILY_CHAT_ID: Optional[int] = (
    int(os.getenv("FAMILY_CHAT_ID")) if os.getenv("FAMILY_CHAT_ID") else None
)
REPORT_CHANNEL_ID: Optional[int] = (
    int(os.getenv("REPORT_CHANNEL_ID")) if os.getenv("REPORT_CHANNEL_ID") else None
)

# Log file path (for file handler and admin "Logs" feature)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR: str = os.path.join(_PROJECT_ROOT, "logs")
LOG_FILE: str = os.path.join(LOG_DIR, "bot.log")
EVENT_LOG_FILE: str = os.path.join(LOG_DIR, "events.log")



