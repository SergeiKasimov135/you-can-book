from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Event, EventStatus, Location, User
from app.repositories import BookingRepository, CategoryRepository, EventRepository, LocationRepository
from app.services.exceptions import AlreadyExistsError, BusinessRuleError, NotFoundError
from app.services.permissions import require_admin, require_event_manager, require_organizer

# Изменение этих полей — повод уведомить клиентов с бронью
_NOTIFY_FIELDS = {"event_date", "location_id"}


@dataclass
class EventChange:
    # Результат изменения мероприятия: что поменялось и кого уведомить

    event: Event
    changes: dict[str, Any] = field(default_factory=dict)
    recipients: list[int] = field(default_factory=list)


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.locations = LocationRepository(session)
        self.categories = CategoryRepository(session)
        self.events = EventRepository(session)
        self.bookings = BookingRepository(session)

    # ---------- Площадки ----------
    async def create_location(
        self, actor: User, name: str, address: str, capacity: int | None = None
    ) -> Location:
        require_admin(actor)
        location = await self.locations.create(name=name, address=address, capacity=capacity)
        await self.session.commit()
        return location

    async def list_locations(self) -> Sequence[Location]:
        return await self.locations.list()

    async def get_location(self, location_id: int) -> Location:
        location = await self.locations.get(location_id)
        if location is None:
            raise NotFoundError(f"Площадка {location_id} не найдена")
        return location

    async def update_location(self, location_id: int, actor: User, **fields: Any) -> Location:
        require_admin(actor)
        location = await self.locations.update(await self.get_location(location_id), **fields)
        await self.session.commit()
        return location

    async def delete_location(self, location_id: int, actor: User) -> None:
        require_admin(actor)
        location = await self.get_location(location_id)
        try:
            async with self.session.begin_nested():  # SAVEPOINT
                await self.locations.delete(location)
        except IntegrityError as exc:  # FK events.location_id ... ON DELETE RESTRICT
            raise BusinessRuleError("Нельзя удалить площадку, на которой есть мероприятия") from exc
        await self.session.commit()

    # ---------- Категории ----------
    async def create_category(self, actor: User, name: str) -> Category:
        require_admin(actor)
        if await self.categories.get_by_name(name):
            raise AlreadyExistsError(f"Категория «{name}» уже существует")
        category = await self.categories.create(name=name)
        await self.session.commit()
        return category

    async def list_categories(self) -> Sequence[Category]:
        return await self.categories.list()

    async def rename_category(self, category_id: int, actor: User, name: str) -> Category:
        require_admin(actor)
        category = await self.categories.get(category_id)
        if category is None:
            raise NotFoundError(f"Категория {category_id} не найдена")
        category = await self.categories.update(category, name=name)
        await self.session.commit()
        return category

    async def delete_category(self, category_id: int, actor: User) -> None:
        # Связи в event_categories удалит БД (ON DELETE CASCADE)
        require_admin(actor)
        category = await self.categories.get(category_id)
        if category is None:
            raise NotFoundError(f"Категория {category_id} не найдена")
        await self.categories.delete(category)
        await self.session.commit()

    # ---------- Мероприятия ----------
    async def _load_categories(self, category_ids: Sequence[int]) -> list[Category]:
        # Минимум одна категория (1..*): БД это не проверит
        if not category_ids:
            raise BusinessRuleError("У мероприятия должна быть хотя бы одна категория")
        categories = list(await self.categories.get_many(category_ids))
        missing = set(category_ids) - {c.id for c in categories}
        if missing:
            raise NotFoundError(f"Категории не найдены: {sorted(missing)}")
        return categories

    async def create_event(
        self,
        actor: User,
        *,
        title: str,
        event_date: datetime,
        location_id: int,
        category_ids: Sequence[int],
        price: Decimal | None = None,
        description: str | None = None,
    ) -> Event:
        # Создатель становится организатором
        require_organizer(actor)
        await self.get_location(location_id)
        categories = await self._load_categories(category_ids)
        event = await self.events.create(
            title=title,
            description=description,
            price=price,
            event_date=event_date,
            location_id=location_id,
            organizer_id=actor.id,
            categories=categories,  # SQLAlchemy сам заполнит event_categories
        )
        await self.session.commit()
        return await self.get_event(event.id)

    async def get_event(self, event_id: int) -> Event:
        event = await self.events.get_with_details(event_id)
        if event is None:
            raise NotFoundError(f"Мероприятие {event_id} не найдено")
        return event

    async def list_catalog(self, *, include_past: bool = False, **filters: Any) -> Sequence[Event]:
        if not include_past and filters.get("date_from") is None:
            filters["date_from"] = datetime.now(timezone.utc)
        return await self.events.list_catalog(**filters)

    async def list_my_events(self, organizer: User) -> Sequence[Event]:
        # Все мероприятия организатора, включая прошедшие и отменённые
        return await self.events.list_catalog(organizer_id=organizer.id, include_cancelled=True)

    async def update_event(
        self, event_id: int, actor: User, *, category_ids: Sequence[int] | None = None, **fields: Any
    ) -> EventChange:
        # Изменение и перенос мероприятия
        event = await self.get_event(event_id)
        require_event_manager(actor, event)
        if event.status == EventStatus.CANCELLED:
            raise BusinessRuleError("Нельзя изменить отменённое мероприятие")
        if "location_id" in fields:
            await self.get_location(fields["location_id"])

        changes = {k: v for k, v in fields.items() if getattr(event, k) != v}
        if category_ids is not None:
            new_categories = await self._load_categories(category_ids)
            if {c.id for c in new_categories} != {c.id for c in event.categories}:
                event.categories = new_categories
                changes["category_ids"] = sorted(category_ids)
        await self.events.update(event, **{k: v for k, v in changes.items() if k in fields})

        recipients: list[int] = []
        if _NOTIFY_FIELDS & changes.keys():
            recipients = await self.bookings.active_user_ids_for_event(event_id)
        await self.session.commit()
        return EventChange(event=await self.get_event(event_id), changes=changes, recipients=recipients)

    async def cancel_event(self, event_id: int, actor: User) -> EventChange:
        # Мероприятие и активные брони отменяются в одной транзакции
        event = await self.get_event(event_id)
        require_event_manager(actor, event)
        if event.status == EventStatus.CANCELLED:
            raise BusinessRuleError("Мероприятие уже отменено")
        await self.events.update(event, status=EventStatus.CANCELLED)
        recipients = await self.bookings.cancel_all_active_for_event(event_id)
        await self.session.commit()
        return EventChange(event=event, changes={"status": EventStatus.CANCELLED}, recipients=recipients)

    async def delete_event(self, event_id: int, actor: User) -> None:
        event = await self.events.get(event_id)
        if event is None:
            raise NotFoundError(f"Мероприятие {event_id} не найдено")
        require_event_manager(actor, event)
        try:
            async with self.session.begin_nested():  # SAVEPOINT
                await self.events.delete(event)
        except IntegrityError as exc:  # FK bookings.event_id ... ON DELETE RESTRICT
            raise BusinessRuleError(
                "Нельзя удалить мероприятие, на которое есть брони. Отмените его вместо удаления"
            ) from exc
        await self.session.commit()
