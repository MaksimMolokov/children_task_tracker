"""
Точка входа Telegram-бота.
Инициализация бота, диспетчера, подключения к БД и планировщика.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import ADMIN_TELEGRAM_ID, BOT_TOKEN, TIMEZONE
from bot.handlers import admin, admin_menu, children, common
from db.database import AsyncSessionLocal, close_db, init_db
from db.models import User, UserRole
from scheduler.jobs import set_bot_instance, setup_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

    # Важно: FSM обработчики должны быть зарегистрированы первыми для правильной работы
    # Роутер children должен быть зарегистрирован раньше admin_menu, чтобы обработчик task_complete не перехватывался
    dp.include_router(children.router)  # Обработчики действий детей (task_complete, медиа)
    dp.include_router(admin_children.router)  # Обработчики для детей (включая FSM)
    dp.include_router(admin_rewards.router)  # Обработчики для карточек заданий (включая FSM)
    dp.include_router(admin_schedules.router)  # Обработчики для расписаний (включая FSM)
    dp.include_router(admin_task_types.router)  # Обработчики для списка карточек заданий
    dp.include_router(admin_testing.router)  # Обработчики для тестирования
    dp.include_router(admin_access.router)  # Обработчики для управления доступами
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(admin_menu.router)  # Админ-меню

    # Инициализация БД и планировщика
    async with lifespan(None):
        logger.info("Бот запущен и готов к работе")
        # Запуск polling
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")

