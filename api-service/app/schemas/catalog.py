from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import EventStatus
from app.schemas.common import ORMModel
from app.schemas.users import UserShort


# ---------- Площадки ----------
class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0)


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0)


class LocationOut(ORMModel):
    id: int
    name: str
    address: str
    capacity: int | None


# ---------- Категории ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class CategoryOut(ORMModel):
    id: int
    name: str


# ---------- Мероприятия ----------
class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    event_date: datetime
    location_id: int
    category_ids: list[int] = Field(min_length=1)


class EventUpdate(BaseModel):
    # Все поля необязательны: меняются только переданные (PATCH)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    event_date: datetime | None = None
    location_id: int | None = None
    category_ids: list[int] | None = Field(default=None, min_length=1)


class EventOut(ORMModel):
    id: int
    title: str
    description: str | None
    price: Decimal | None
    event_date: datetime
    status: EventStatus
    location: LocationOut
    categories: list[CategoryOut]
    organizer: UserShort | None


class EventChangeOut(BaseModel):
    # Ответ на изменение/отмену: кого из клиентов нужно уведомить
    event: EventOut
    changes: list[str]
    notify_user_ids: list[int]
