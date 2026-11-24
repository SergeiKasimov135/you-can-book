# Внедрение зависимостей FastAPI: сессия БД -> сервисы -> текущий пользователь
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User, UserRole
from app.repositories import UserRepository
from app.security import decode_access_token
from app.services import BookingService, CatalogService, FeedbackService, FriendService, UserService

# Одна сессия на запрос: get_session открывает её до обработчика и закрывает после (yield)
DbSession = Annotated[AsyncSession, Depends(get_session)]


def get_user_service(session: DbSession) -> UserService:
    return UserService(session)


def get_catalog_service(session: DbSession) -> CatalogService:
    return CatalogService(session)


def get_booking_service(session: DbSession) -> BookingService:
    return BookingService(session)


def get_friend_service(session: DbSession) -> FriendService:
    return FriendService(session)


def get_feedback_service(session: DbSession) -> FeedbackService:
    return FeedbackService(session)


Users = Annotated[UserService, Depends(get_user_service)]
Catalog = Annotated[CatalogService, Depends(get_catalog_service)]
Bookings = Annotated[BookingService, Depends(get_booking_service)]
Friends = Annotated[FriendService, Depends(get_friend_service)]
Feedback = Annotated[FeedbackService, Depends(get_feedback_service)]

# Токен берётся из заголовка Authorization: Bearer <token>; tokenUrl — для кнопки Authorize в Swagger
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Требуется вход: неверный или просроченный токен",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: DbSession) -> User:
    try:
        user_id = decode_access_token(token)
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTHORIZED from None
    # Пользователь читается из БД: удалённый аккаунт или новая роль учитываются сразу
    user = await UserRepository(session).get(user_id)
    if user is None:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    # Фабрика зависимостей: пускает только указанные роли (авторизация)
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав для этого действия")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
OrganizerUser = Annotated[User, Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))]
