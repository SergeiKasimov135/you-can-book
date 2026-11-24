from collections.abc import Sequence

from sqlalchemy import select

from app.models import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id))

    async def list_by_role(self, role: UserRole) -> Sequence[User]:
        stmt = select(User).where(User.role == role).order_by(User.id)
        return (await self.session.scalars(stmt)).all()
