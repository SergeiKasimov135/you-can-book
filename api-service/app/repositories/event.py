from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Booking, BookingStatus, Event, EventStatus, event_categories
from app.repositories.base import BaseRepository

# Связанные объекты, которые нужны почти всегда при показе мероприятия.
# selectinload подгружает их отдельным запросом SELECT ... WHERE id IN (...)
# сразу для всех мероприятий — без проблемы N+1 и без ленивой загрузки,
# которая в async-режиме не работает.
_WITH_DETAILS = (selectinload(Event.location), selectinload(Event.categories))


class EventRepository(BaseRepository[Event]):
    model = Event

    async def get_with_details(self, event_id: int) -> Event | None:
        stmt = select(Event).where(Event.id == event_id).options(*_WITH_DETAILS)
        return await self.session.scalar(stmt)

    async def list_catalog(
        self,
        *,
        category_id: int | None = None,
        location_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        include_cancelled: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Event]:
        """Каталог с фильтрами. Каждый фильтр добавляет условие WHERE, только если задан."""
        stmt = select(Event).options(*_WITH_DETAILS)
        if category_id is not None:
            stmt = stmt.join(event_categories).where(event_categories.c.category_id == category_id)
        if location_id is not None:
            stmt = stmt.where(Event.location_id == location_id)
        if date_from is not None:
            stmt = stmt.where(Event.event_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Event.event_date <= date_to)
        if not include_cancelled:
            stmt = stmt.where(Event.status == EventStatus.SCHEDULED)
        stmt = stmt.order_by(Event.event_date).offset(offset).limit(limit)
        return (await self.session.scalars(stmt)).all()

    async def list_recommendation_candidates(
        self, user_id: int, now: datetime, limit: int = 50
    ) -> Sequence[Event]:
        """Будущие мероприятия, на которые у клиента ещё нет активной брони.

        Используется как список кандидатов для сервиса рекомендаций (ЛР3).
        """
        already_booked = select(Booking.event_id).where(
            Booking.user_id == user_id, Booking.status == BookingStatus.BOOKED
        )
        stmt = (
            select(Event)
            .options(selectinload(Event.categories))
            .where(
                Event.status == EventStatus.SCHEDULED,
                Event.event_date > now,
                Event.id.not_in(already_booked),
            )
            .order_by(Event.event_date)
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all()
