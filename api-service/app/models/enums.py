"""Перечисления статусов и ролей.

В БД они хранятся как VARCHAR + CHECK-ограничение (а не как ENUM-тип PostgreSQL):
так проще добавлять новые значения миграциями.
"""
from enum import Enum

from sqlalchemy import Enum as SAEnum


class UserRole(str, Enum):
    CLIENT = "CLIENT"
    ADMIN = "ADMIN"


class EventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"


class BookingStatus(str, Enum):
    BOOKED = "BOOKED"
    CANCELLED = "CANCELLED"
    ATTENDED = "ATTENDED"


def varchar_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Тип колонки: VARCHAR(20) с CHECK (value IN (...))."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )
