from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.enums import EventStatus, varchar_enum

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.category import Category
    from app.models.location import Location
    from app.models.user import User

# M:N мероприятие — категория; составной PK не даёт привязать категорию дважды
event_categories = Table(
    "event_categories",
    Base.metadata,
    Column("event_id", ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Event(CreatedAtMixin, Base):
    __tablename__ = "events"
    __table_args__ = (CheckConstraint("price >= 0", name="price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # справочно, оплата на месте
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[EventStatus] = mapped_column(
        varchar_enum(EventStatus, "status"),
        default=EventStatus.SCHEDULED,
        server_default=EventStatus.SCHEDULED.value,
    )
    # При удалении организатора мероприятие остаётся (SET NULL)
    organizer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    location: Mapped["Location"] = relationship(back_populates="events")
    organizer: Mapped["User | None"] = relationship()
    # Связи event_categories удаляет БД (CASCADE)
    categories: Mapped[list["Category"]] = relationship(
        secondary=event_categories,
        back_populates="events",
        order_by="Category.name",
        passive_deletes=True,
    )
    # Брони не трогаем: удаление мероприятия с бронями запретит БД (RESTRICT)
    bookings: Mapped[list["Booking"]] = relationship(back_populates="event", passive_deletes="all")
