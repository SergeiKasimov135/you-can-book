from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import UserRole
from app.schemas.common import ORMModel


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)


class RoleUpdate(BaseModel):
    role: UserRole


class UserShort(ORMModel):
    id: int
    full_name: str | None


class UserOut(ORMModel):
    # Пароль (даже хеш) в ответ не попадает
    id: int
    email: EmailStr
    full_name: str | None
    role: UserRole
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
