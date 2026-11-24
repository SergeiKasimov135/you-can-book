from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models import Booking, BookingStatus, Event
from app.repositories.base import BaseRepository

_WITH_EVENT = (
    selectinload(Booking.event).selectinload(Event.location),
    selectinload(Booking.user),
)


class BookingRepository(BaseRepository[Booking]):
    model = Booking

    async def get_with_details(self, booking_id: int) -> Booking | None:
        stmt = select(Booking).where(Booking.id == booking_id).options(*_WITH_EVENT)
        return await self.session.scalar(stmt)

    async def get_active(self, user_id: int, event_id: int) -> Booking | None:
        stmt = select(Booking).where(
            Booking.user_id == user_id,
            Booking.event_id == event_id,
            Booking.status == BookingStatus.BOOKED,
        )
        return await self.session.scalar(stmt)

    async def list_filtered(
        self,
        *,
        user_id: int | None = None,
        event_id: int | None = None,
        status: BookingStatus | None = None,
    ) -> Sequence[Booking]:
        stmt = select(Booking).join(Booking.event).options(*_WITH_EVENT)
        if user_id is not None:
            stmt = stmt.where(Booking.user_id == user_id)
        if event_id is not None:
            stmt = stmt.where(Booking.event_id == event_id)
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        stmt = stmt.order_by(Event.event_date, Booking.id)
        return (await self.session.scalars(stmt)).all()

    async def active_user_ids_for_event(self, event_id: int) -> list[int]:
        # Кому слать уведомление о переносе мероприятия
        stmt = (
            select(Booking.user_id)
            .where(Booking.event_id == event_id, Booking.status == BookingStatus.BOOKED)
            .order_by(Booking.user_id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def cancel_all_active_for_event(self, event_id: int) -> list[int]:
        # Один UPDATE ... RETURNING user_id
        stmt = (
            update(Booking)
            .where(Booking.event_id == event_id, Booking.status == BookingStatus.BOOKED)
            .values(status=BookingStatus.CANCELLED)
            .returning(Booking.user_id)
            .execution_options(synchronize_session="fetch")
        )
        return sorted((await self.session.scalars(stmt)).all())
