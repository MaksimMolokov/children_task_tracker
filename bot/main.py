"""
Точка входа Telegram-бота.
Инициализация бота, диспетчера, подключения к БД и планировщика.
"""
import asyncio
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import ADMIN_TELEGRAM_ID, BOT_TOKEN, TIMEZONE
from bot.utils.event_log import log_event
from bot.handlers import admin, admin_menu, children, common
from bot.middleware.auth import AdminMiddleware
from db.database import AsyncSessionLocal, close_db, init_db
from db.models import User, UserRole
from scheduler.jobs import set_bot_instance, setup_scheduler

# Настройка логирования: консоль + файл с ротацией
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Файл логов (директория logs в корне проекта)
from bot.config import LOG_DIR, LOG_FILE
if not os.path.isdir(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)
file_handler = TimedRotatingFileHandler(
    LOG_FILE, when="midnight", interval=1, backupCount=7, encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logging.getLogger().addHandler(file_handler)


@asynccontextmanager
async def lifespan(app):
    """Lifecycle приложения: инициализация и очистка ресурсов"""
    # Инициализация
    logger.info("Инициализация приложения...")
    await init_db()
    logger.info("База данных инициализирована")

    # Гарантируем, что пользователь из ADMIN_TELEGRAM_ID есть в БД как активный админ
    if ADMIN_TELEGRAM_ID:
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_user_id == ADMIN_TELEGRAM_ID)
            )
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    telegram_user_id=ADMIN_TELEGRAM_ID,
                    role=UserRole.ADMIN,
                    display_name="Админ",
                    is_active=True,
                )
                session.add(user)
                await session.commit()
                logger.info("Создан админ из ADMIN_TELEGRAM_ID: %s", ADMIN_TELEGRAM_ID)
            elif user.role != UserRole.ADMIN or not user.is_active:
                user.role = UserRole.ADMIN
                user.is_active = True
                await session.commit()
                logger.info("Обновлён админ из ADMIN_TELEGRAM_ID: %s", ADMIN_TELEGRAM_ID)

    # Настройка планировщика
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Планировщик запущен")

    yield

    # Очистка
    logger.info("Остановка приложения...")
    scheduler.shutdown()
    await close_db()
    logger.info("Приложение остановлено")


async def main():
    """
    Главная функция запуска бота.
    См. SPEC.md раздел 2.2 "Компоненты"
    """
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Устанавливаем bot instance для использования в scheduler
    set_bot_instance(bot)

    # Регистрация роутеров (handlers)
    # См. SPEC.md раздел 4 "Логика и поведение" и раздел 7 "Админ-меню"
    from bot.handlers import admin_children, admin_rewards, admin_schedules, admin_task_types, admin_testing, admin_access

    # Важно: роутер children должен быть зарегистрирован раньше admin_menu, чтобы обработчик task_complete не перехватывался
    dp.include_router(children.router)  # Обработчики действий детей (task_complete, медиа)

    # Админ-роутеры: AdminMiddleware подключён один раз к группе
    admin_router = Router()
    admin_router.callback_query.middleware(AdminMiddleware())
    admin_router.message.middleware(AdminMiddleware())
    admin_router.include_router(admin_children.router)
    admin_router.include_router(admin_rewards.router)
    admin_router.include_router(admin_schedules.router)
    admin_router.include_router(admin_task_types.router)
    admin_router.include_router(admin_testing.router)
    admin_router.include_router(admin_access.router)
    admin_router.include_router(admin.router)
    admin_router.include_router(admin_menu.router)
    dp.include_router(admin_router)

    dp.include_router(common.router)

    # Инициализация БД и планировщика
    async with lifespan(None):
        logger.info("Бот запущен и готов к работе")
        log_event("Бот запущен")
        try:
            await bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text="Бот запущен")
        except Exception as e:
            logger.warning("Не удалось отправить уведомление админу о запуске: %s", e)
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")

