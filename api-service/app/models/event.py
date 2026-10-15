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

# Связующая таблица M:N «мероприятие — категория». Собственных атрибутов у связи нет,
# поэтому это просто Table, а не модель. Составной первичный ключ (event_id, category_id)
# не даёт привязать одну категорию к мероприятию дважды.
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

    location: Mapped["Location"] = relationship(back_populates="events")
    # Категории всегда отсортированы по названию.
    # passive_deletes=True: строки event_categories при удалении мероприятия
    # удаляет сама БД (ON DELETE CASCADE).
    categories: Mapped[list["Category"]] = relationship(
        secondary=event_categories,
        back_populates="events",
        order_by="Category.name",
        passive_deletes=True,
    )
    # passive_deletes="all": SQLAlchemy не трогает брони при удалении мероприятия
    # (иначе он попытался бы обнулить bookings.event_id). Решение принимает БД:
    # FK ... ON DELETE RESTRICT запретит удаление, если брони есть.
    bookings: Mapped[list["Booking"]] = relationship(back_populates="event", passive_deletes="all")
