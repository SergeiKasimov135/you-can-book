from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole
from app.repositories import UserRepository
from app.security import hash_password, verify_password
from app.services.exceptions import AlreadyExistsError, NotFoundError


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(
        self, email: str, password: str, full_name: str | None = None, role: UserRole = UserRole.CLIENT
    ) -> User:
        email = email.strip().lower()
        if await self.users.get_by_email(email):
            raise AlreadyExistsError(f"Пользователь с email {email} уже существует")
        user = await self.users.create(
            email=email, hashed_password=hash_password(password), full_name=full_name, role=role
        )
        await self.session.commit()
        return user

    async def authenticate(self, email: str, password: str) -> User | None:
        """Проверка логина и пароля. В ЛР2 при успехе будет выдаваться JWT."""
        user = await self.users.get_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user

    async def get(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"Пользователь {user_id} не найден")
        return user

    async def list(self, role: UserRole | None = None) -> Sequence[User]:
        return await (self.users.list_by_role(role) if role else self.users.list())

    async def update_profile(self, user_id: int, full_name: str) -> User:
        user = await self.users.update(await self.get(user_id), full_name=full_name)
        await self.session.commit()
        return user

    async def delete(self, user_id: int) -> None:
        """Удаление пользователя. Его брони удалит сама БД (ON DELETE CASCADE)."""
        await self.users.delete(await self.get(user_id))
        await self.session.commit()
