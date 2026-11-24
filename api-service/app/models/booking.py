from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.enums import BookingStatus, varchar_enum

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.user import User


class Booking(CreatedAtMixin, Base):
    # Бронь — связь M:N User ↔ Event со своими атрибутами

    __tablename__ = "bookings"
    __table_args__ = (
        # Не больше одной активной брони клиента на мероприятие
        Index(
            "ux_bookings_active",
            "user_id",
            "event_id",
            unique=True,
            postgresql_where=text("status = 'BOOKED'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="RESTRICT"), index=True)
    status: Mapped[BookingStatus] = mapped_column(
        varchar_enum(BookingStatus, "status"),
        default=BookingStatus.BOOKED,
        server_default=BookingStatus.BOOKED.value,
    )
    comment: Mapped[str | None] = mapped_column(String(255))

    user: Mapped["User"] = relationship(back_populates="bookings")
    event: Mapped["Event"] = relationship(back_populates="bookings")
