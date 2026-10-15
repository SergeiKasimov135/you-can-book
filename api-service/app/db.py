from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

# Пул соединений, один на приложение
engine = create_async_engine(settings.database_url, echo=settings.sql_echo, pool_pre_ping=True)

# expire_on_commit=False: объекты доступны после commit (в async нет ленивой загрузки)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
