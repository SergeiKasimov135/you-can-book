"""Обобщённый репозиторий с CRUD-операциями.

Репозиторий только читает и изменяет объекты в рамках сессии (flush),
но не фиксирует транзакцию. Commit делает сервисный слой: он знает,
где заканчивается бизнес-операция.
"""
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Read ---
    async def get(self, obj_id: int) -> ModelT | None:
        return await self.session.get(self.model, obj_id)

    async def list(self, *, offset: int = 0, limit: int = 100) -> Sequence[ModelT]:
        stmt = select(self.model).order_by(self.model.id).offset(offset).limit(limit)
        return (await self.session.scalars(stmt)).all()

    async def count(self) -> int:
        return await self.session.scalar(select(func.count()).select_from(self.model))

    # --- Create ---
    async def create(self, **fields: Any) -> ModelT:
        obj = self.model(**fields)
        self.session.add(obj)
        await self.session.flush()  # INSERT выполняется сейчас, obj получает id
        return obj

    # --- Update ---
    async def update(self, obj: ModelT, **fields: Any) -> ModelT:
        for name, value in fields.items():
            setattr(obj, name, value)
        await self.session.flush()  # UPDATE только изменённых полей
        return obj

    # --- Delete ---
    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()
