"""
Подключение к базе данных PostgreSQL через SQLAlchemy (async).
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import DATABASE_URL

# Создание async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Установить True для отладки SQL запросов
    future=True,
)

# Создание session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency для получения сессии БД.
    Использовать в обработчиках как:
        async with get_db() as session:
            # работа с БД
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Инициализация БД: создание всех таблиц.
    Вызывать при старте приложения.
    """
    from db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """
    Закрытие соединений с БД.
    Вызывать при остановке приложения.
    """
    await engine.dispose()



