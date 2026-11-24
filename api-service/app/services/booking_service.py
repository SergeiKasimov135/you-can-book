from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingStatus, Event, EventStatus, User, UserRole
from app.repositories import BookingRepository, EventRepository
from app.services.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.services.permissions import require_event_manager


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bookings = BookingRepository(session)
        self.events = EventRepository(session)

    async def check_bookable(self, user_id: int, event_id: int) -> Event:
        # Проверки перед бронированием
        event = await self.events.get(event_id)
        if event is None:
            raise NotFoundError(f"Мероприятие {event_id} не найдено")
        if event.status != EventStatus.SCHEDULED:
            raise BusinessRuleError("Мероприятие отменено, бронирование невозможно")
        if event.event_date <= datetime.now(timezone.utc):
            raise BusinessRuleError("Мероприятие уже прошло")
        if await self.bookings.get_active(user_id, event_id):
            raise BusinessRuleError("У вас уже есть активная бронь на это мероприятие")
        return event

    async def book(self, user_id: int, event_id: int, comment: str | None = None) -> Booking:
        await self.check_bookable(user_id, event_id)
        try:
            # SAVEPOINT: при ошибке откатывается только этот INSERT
            async with self.session.begin_nested():
                booking = await self.bookings.create(user_id=user_id, event_id=event_id, comment=comment)
        except IntegrityError as exc:
            # Гонка двух запросов: ux_bookings_active пропустит только один
            raise BusinessRuleError("У вас уже есть активная бронь на это мероприятие") from exc
        await self.session.commit()
        return await self.get(booking.id)

    async def get(self, booking_id: int) -> Booking:
        booking = await self.bookings.get_with_details(booking_id)
        if booking is None:
            raise NotFoundError(f"Бронь {booking_id} не найдена")
        return booking

    async def cancel(self, booking_id: int, actor: User) -> Booking:
        # Владелец брони или администратор
        booking = await self.get(booking_id)
        if actor.role != UserRole.ADMIN and booking.user_id != actor.id:
            raise PermissionDeniedError("Можно отменить только свою бронь")
        if booking.status != BookingStatus.BOOKED:
            raise BusinessRuleError(f"Бронь в статусе {booking.status.value} нельзя отменить")
        await self.bookings.update(booking, status=BookingStatus.CANCELLED)
        await self.session.commit()
        return booking

    async def mark_attended(self, booking_id: int, actor: User) -> Booking:
        # Организатор или администратор отмечает приход клиента
        booking = await self.get(booking_id)
        require_event_manager(actor, booking.event)
        if booking.status != BookingStatus.BOOKED:
            raise BusinessRuleError(f"Бронь в статусе {booking.status.value} нельзя отметить")
        await self.bookings.update(booking, status=BookingStatus.ATTENDED)
        await self.session.commit()
        return booking

    async def list_my(self, user_id: int) -> Sequence[Booking]:
        return await self.bookings.list_filtered(user_id=user_id)

    async def list_for_event(self, event_id: int, actor: User) -> Sequence[Booking]:
        # Список гостей — для организатора или администратора
        event = await self.events.get(event_id)
        if event is None:
            raise NotFoundError(f"Мероприятие {event_id} не найдено")
        require_event_manager(actor, event)
        return await self.bookings.list_filtered(event_id=event_id)

    async def list_for_admin(
        self,
        *,
        user_id: int | None = None,
        event_id: int | None = None,
        status: BookingStatus | None = None,
    ) -> Sequence[Booking]:
        return await self.bookings.list_filtered(user_id=user_id, event_id=event_id, status=status)
