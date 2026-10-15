from collections.abc import Sequence

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import selectinload

from app.models import Booking, BookingStatus, Category, Event, event_categories
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
        """Брони с фильтрами: свои (клиент) или любого клиента / мероприятия (администратор)."""
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
        """Кому слать уведомление о переносе мероприятия."""
        stmt = (
            select(Booking.user_id)
            .where(Booking.event_id == event_id, Booking.status == BookingStatus.BOOKED)
            .order_by(Booking.user_id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def cancel_all_active_for_event(self, event_id: int) -> list[int]:
        """Массовая отмена броней одним запросом UPDATE ... RETURNING user_id.

        Возвращает id клиентов, чьи брони были отменены (получатели уведомления).
        """
        stmt = (
            update(Booking)
            .where(Booking.event_id == event_id, Booking.status == BookingStatus.BOOKED)
            .values(status=BookingStatus.CANCELLED)
            .returning(Booking.user_id)
            .execution_options(synchronize_session="fetch")
        )
        return sorted((await self.session.scalars(stmt)).all())

    async def category_stats_for_user(self, user_id: int) -> list[tuple[int, str, int]]:
        """Статистика интересов клиента по категориям для рекомендаций.

        Посещённое мероприятие (ATTENDED) весит 2, активная бронь (BOOKED) — 1,
        отменённые брони не учитываются. Возвращает (category_id, name, weight).
        """
        weight = func.sum(case((Booking.status == BookingStatus.ATTENDED, 2), else_=1))
        stmt = (
            select(Category.id, Category.name, weight.label("weight"))
            .select_from(Booking)
            .join(event_categories, event_categories.c.event_id == Booking.event_id)
            .join(Category, Category.id == event_categories.c.category_id)
            .where(Booking.user_id == user_id, Booking.status != BookingStatus.CANCELLED)
            .group_by(Category.id, Category.name)
            .order_by(weight.desc(), Category.name)
        )
        return [(row.id, row.name, int(row.weight)) for row in await self.session.execute(stmt)]
