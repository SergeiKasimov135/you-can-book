"""Все модели импортируются здесь, чтобы Alembic видел полную схему в Base.metadata."""
from app.models.base import Base
from app.models.booking import Booking
from app.models.category import Category
from app.models.enums import BookingStatus, EventStatus, UserRole
from app.models.event import Event, event_categories
from app.models.location import Location
from app.models.user import User

__all__ = [
    "Base",
    "Booking",
    "BookingStatus",
    "Category",
    "Event",
    "EventStatus",
    "Location",
    "User",
    "UserRole",
    "event_categories",
]
