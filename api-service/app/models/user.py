from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.enums import UserRole, varchar_enum

if TYPE_CHECKING:
    from app.models.booking import Booking


class User(CreatedAtMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(
        varchar_enum(UserRole, "role"), default=UserRole.CLIENT, server_default=UserRole.CLIENT.value
    )

    # Брони пользователя. passive_deletes=True: удаление броней при удалении
    # пользователя выполняет сама БД (ON DELETE CASCADE), а не SQLAlchemy.
    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
