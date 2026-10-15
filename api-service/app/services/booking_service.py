"""Бронирование мест: сценарии клиента и администратора."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingStatus, Event, EventStatus, User, UserRole
from app.repositories import BookingRepository, EventRepository
from app.services.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError


@dataclass
class RecommendationInput:
    """Данные, которые API Service передаст по gRPC сервису рекомендаций (ЛР3)."""

    user_id: int
    history: list[tuple[int, str, int]]  # (category_id, category_name, weight)
    candidates: Sequence[Event]


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bookings = BookingRepository(session)
        self.events = EventRepository(session)

    async def book(self, user_id: int, event_id: int, comment: str | None = None) -> Booking:
        """Забронировать место. Оплата производится на месте, количество мест не учитывается."""
        event = await self.events.get(event_id)
        if event is None:
            raise NotFoundError(f"Мероприятие {event_id} не найдено")
        if event.status != EventStatus.SCHEDULED:
            raise BusinessRuleError("Мероприятие отменено, бронирование невозможно")
        if event.event_date <= datetime.now(timezone.utc):
            raise BusinessRuleError("Мероприятие уже прошло")
        if await self.bookings.get_active(user_id, event_id):
            raise BusinessRuleError("У вас уже есть активная бронь на это мероприятие")

        try:
            booking = await self.bookings.create(user_id=user_id, event_id=event_id, comment=comment)
            await self.session.commit()
        except IntegrityError as exc:
            # Страховка от гонки: два одновременных запроса прошли проверку выше,
            # но частичный уникальный индекс ux_bookings_active пропустит только один INSERT
            await self.session.rollback()
            raise BusinessRuleError("У вас уже есть активная бронь на это мероприятие") from exc
        return await self.get(booking.id)

    async def get(self, booking_id: int) -> Booking:
        booking = await self.bookings.get_with_details(booking_id)
        if booking is None:
            raise NotFoundError(f"Бронь {booking_id} не найдена")
        return booking

    async def cancel(self, booking_id: int, actor: User) -> Booking:
        """Отменить бронь может её владелец или администратор."""
        booking = await self.get(booking_id)
        if actor.role != UserRole.ADMIN and booking.user_id != actor.id:
            raise PermissionDeniedError("Можно отменить только свою бронь")
        if booking.status != BookingStatus.BOOKED:
            raise BusinessRuleError(f"Бронь в статусе {booking.status.value} нельзя отменить")
        await self.bookings.update(booking, status=BookingStatus.CANCELLED)
        await self.session.commit()
        return booking

    async def mark_attended(self, booking_id: int) -> Booking:
        """Администратор отмечает, что клиент пришёл на мероприятие."""
        booking = await self.get(booking_id)
        if booking.status != BookingStatus.BOOKED:
            raise BusinessRuleError(f"Бронь в статусе {booking.status.value} нельзя отметить")
        await self.bookings.update(booking, status=BookingStatus.ATTENDED)
        await self.session.commit()
        return booking

    async def list_my(self, user_id: int) -> Sequence[Booking]:
        return await self.bookings.list_filtered(user_id=user_id)

    async def list_for_admin(
        self,
        *,
        user_id: int | None = None,
        event_id: int | None = None,
        status: BookingStatus | None = None,
    ) -> Sequence[Booking]:
        return await self.bookings.list_filtered(user_id=user_id, event_id=event_id, status=status)

    async def recommendation_input(self, user_id: int) -> RecommendationInput:
        return RecommendationInput(
            user_id=user_id,
            history=await self.bookings.category_stats_for_user(user_id),
            candidates=await self.events.list_recommendation_candidates(
                user_id, now=datetime.now(timezone.utc)
            ),
        )
