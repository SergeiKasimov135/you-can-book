from collections.abc import Iterable, Sequence

from sqlalchemy import select

from app.models import Category
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    model = Category

    async def get_by_name(self, name: str) -> Category | None:
        return await self.session.scalar(select(Category).where(Category.name == name))

    async def get_many(self, ids: Iterable[int]) -> Sequence[Category]:
        stmt = select(Category).where(Category.id.in_(list(ids))).order_by(Category.id)
        return (await self.session.scalars(stmt)).all()
