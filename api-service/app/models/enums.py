from enum import Enum

from sqlalchemy import Enum as SAEnum


class UserRole(str, Enum):
    CLIENT = "CLIENT"
    ORGANIZER = "ORGANIZER"  # ведёт свои мероприятия
    ADMIN = "ADMIN"  # управляет всем каталогом


class EventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"


class BookingStatus(str, Enum):
    BOOKED = "BOOKED"
    CANCELLED = "CANCELLED"
    ATTENDED = "ATTENDED"


class FriendshipStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class InvitationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class FeedbackCriterion(str, Enum):
    # Критерии отзыва

    AUDIENCE = "AUDIENCE"
    CULTURE = "CULTURE"
    ORGANIZATION = "ORGANIZATION"
    VENUE = "VENUE"
    PROGRAM = "PROGRAM"


# Код -> (название, вопрос пользователю)
CRITERION_QUESTIONS: dict[FeedbackCriterion, tuple[str, str]] = {
    FeedbackCriterion.AUDIENCE: ("Аудитория", "Публика и атмосфера в зале были приятными?"),
    FeedbackCriterion.CULTURE: ("Культурность", "Мероприятие было содержательным и культурным?"),
    FeedbackCriterion.ORGANIZATION: ("Организация", "Вход, начало вовремя и работа персонала — без проблем?"),
    FeedbackCriterion.VENUE: ("Площадка", "На площадке удобно: звук, видимость, чистота?"),
    FeedbackCriterion.PROGRAM: ("Программа", "Программа соответствовала анонсу?"),
}


def varchar_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    # Тип колонки: VARCHAR(20) с CHECK (value IN (...))
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )
