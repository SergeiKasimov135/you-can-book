"""Подключение к PostgreSQL: асинхронный движок и фабрика сессий."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

# Engine держит пул соединений с БД. Создаётся один раз на всё приложение.
engine = create_async_engine(settings.database_url, echo=settings.sql_echo, pool_pre_ping=True)

# Фабрика сессий. Сессия = единица работы (unit of work): набор изменений,
# которые фиксируются одним commit или откатываются rollback.
# expire_on_commit=False — объекты остаются доступными после commit
# (в async-режиме ленивая подгрузка атрибутов после commit невозможна).
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Выдаёт сессию и гарантированно закрывает её. В ЛР2 станет зависимостью FastAPI."""
    async with SessionFactory() as session:
        yield session
