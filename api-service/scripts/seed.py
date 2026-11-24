import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.db import SessionFactory, engine
from app.models import (
    BookingStatus,
    EventFeedback,
    EventInvitation,
    FeedbackCriterion,
    FeedbackScore,
    Friendship,
    FriendshipStatus,
    UserRole,
)
from app.repositories import (
    BookingRepository,
    CategoryRepository,
    EventRepository,
    LocationRepository,
    UserRepository,
)
from app.security import hash_password
from sqlalchemy import text

# Самара, UTC+4 (без zoneinfo, чтобы на Windows не нужен был tzdata)
LOCAL_TZ = timezone(timedelta(hours=4))

DEFAULT_PASSWORD = "password123"

USERS = [
    # email, ФИО, роль
    ("admin@ycb.ru", "Администратор Агентства", UserRole.ADMIN),
    ("ivan@ycb.ru", "Иван Петров", UserRole.CLIENT),
    ("olga@ycb.ru", "Ольга Смирнова", UserRole.CLIENT),
    ("pavel@ycb.ru", "Павел Кузнецов", UserRole.CLIENT),
    # организаторы
    ("dmitry@ycb.ru", "Дмитрий Орлов (организатор концертов)", UserRole.ORGANIZER),
    ("anna@ycb.ru", "Анна Белова (организатор лекций)", UserRole.ORGANIZER),
]

# индекс площадки -> email организатора
ORGANIZER_BY_LOCATION = {0: "dmitry@ycb.ru", 1: "anna@ycb.ru", 2: "dmitry@ycb.ru", 3: "dmitry@ycb.ru"}

LOCATIONS = [
    # название, адрес, вместимость
    ("Концертный зал «Променад»", "г. Самара, ул. Набережная, 10", 800),
    ("Лекторий «Пространство»", "г. Самара, ул. Университетская, 5", 120),
    ("Театр «Бенефис»", "г. Самара, ул. Театральная, 3", 350),
    ("Парк «Зелёный берег»", "г. Самара, пр. Парковый, 1", None),
]

CATEGORIES = ["Концерты", "Лекции", "Спектакли", "Выставки", "Фестивали", "Стендап"]

# название, через сколько дней (отрицательное — прошедшее), часы, площадка, категории, цена
EVENTS = [
    ("Джазовый вечер", 7, 19, 0, ["Концерты"], Decimal("1500.00")),
    ("Симфонический оркестр: Чайковский", 14, 19, 0, ["Концерты"], Decimal("2500.00")),
    ("Лекция «Как устроен интернет»", 3, 18, 1, ["Лекции"], None),
    ("Лекция «История джаза»", 10, 18, 1, ["Лекции", "Концерты"], Decimal("300.00")),
    ("Спектакль «Вишнёвый сад»", 5, 19, 2, ["Спектакли"], Decimal("1800.00")),
    ("Импровизация: стендап-вечер", 12, 20, 2, ["Стендап"], Decimal("700.00")),
    ("Фестиваль уличной еды", 20, 12, 3, ["Фестивали"], None),
    ("Выставка современной фотографии", 4, 11, 1, ["Выставки"], Decimal("400.00")),
    ("Open Air: инди-рок", 25, 17, 3, ["Концерты", "Фестивали"], Decimal("2000.00")),
    # прошедшие мероприятия — для истории посещений
    ("Рок-концерт «Осень»", -20, 19, 0, ["Концерты"], Decimal("1200.00")),
    ("Лекция «Нейросети без формул»", -10, 18, 1, ["Лекции"], None),
]

# email клиента, индекс мероприятия, статус, комментарий
BOOKINGS = [
    ("ivan@ycb.ru", 9, BookingStatus.ATTENDED, None),
    ("ivan@ycb.ru", 0, BookingStatus.BOOKED, "Буду с другом"),
    ("ivan@ycb.ru", 4, BookingStatus.BOOKED, None),
    ("olga@ycb.ru", 10, BookingStatus.ATTENDED, None),
    ("olga@ycb.ru", 2, BookingStatus.BOOKED, None),
    ("olga@ycb.ru", 0, BookingStatus.BOOKED, "Нужно место у прохода"),
    ("pavel@ycb.ru", 5, BookingStatus.BOOKED, None),
    ("pavel@ycb.ru", 9, BookingStatus.CANCELLED, "Не смог прийти"),
    # посетители прошедших мероприятий (для отзывов)
    ("olga@ycb.ru", 9, BookingStatus.ATTENDED, None),
    ("pavel@ycb.ru", 10, BookingStatus.ATTENDED, None),
]

# (кто отправил заявку, кому, статус)
FRIENDSHIPS = [
    ("ivan@ycb.ru", "olga@ycb.ru", FriendshipStatus.ACCEPTED),
    ("olga@ycb.ru", "pavel@ycb.ru", FriendshipStatus.ACCEPTED),
    ("pavel@ycb.ru", "ivan@ycb.ru", FriendshipStatus.PENDING),  # Иван ещё не ответил
]

# (кто, кого, индекс мероприятия, сообщение)
INVITATIONS = [
    ("olga@ycb.ru", "ivan@ycb.ru", 2, "Пойдём на лекцию? Я уже записалась"),
]

C = FeedbackCriterion

# (email, индекс мероприятия, {критерий: хорошо/плохо}, комментарий); неотмеченных критериев нет в словаре
FEEDBACK = [
    (
        "ivan@ycb.ru", 9,
        {C.AUDIENCE: True, C.CULTURE: True, C.ORGANIZATION: False, C.VENUE: True},
        "Отличный звук, но на входе была очередь",
    ),
    (
        "olga@ycb.ru", 9,
        {C.AUDIENCE: True, C.ORGANIZATION: False, C.PROGRAM: True},
        None,
    ),
    (
        "olga@ycb.ru", 10,
        {C.CULTURE: True, C.ORGANIZATION: True, C.PROGRAM: True},
        "Понятно даже без технического образования",
    ),
]


async def check_schema() -> None:
    # Без последней миграции seed упадёт на отсутствующих таблицах
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    head = ScriptDirectory.from_config(Config(str(ini))).get_current_head()
    async with engine.connect() as conn:
        current = None
        if await conn.scalar(text("SELECT to_regclass('alembic_version')")):
            current = await conn.scalar(text("SELECT version_num FROM alembic_version"))
    if current != head:
        raise SystemExit(
            f"Схема БД на версии {current or '(пусто)'}, а нужна {head}. "
            "Сначала выполните: alembic upgrade head"
        )


async def clear_database() -> None:
    # Очистка таблиц и сброс id
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE feedback_scores, event_feedback, event_invitations, "
                "friendships, bookings, event_categories, events, categories, locations, users "
                "RESTART IDENTITY CASCADE"
            )
        )


async def seed() -> None:
    await check_schema()
    await clear_database()
    now = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)
    hashed = hash_password(DEFAULT_PASSWORD)  # bcrypt медленный — один хеш на всех

    async with SessionFactory() as session:
        users_repo = UserRepository(session)
        users = {
            email: await users_repo.create(
                email=email, hashed_password=hashed, full_name=name, role=role
            )
            for email, name, role in USERS
        }

        locations = [
            await LocationRepository(session).create(name=n, address=a, capacity=c)
            for n, a, c in LOCATIONS
        ]

        categories_repo = CategoryRepository(session)
        categories = {name: await categories_repo.create(name=name) for name in CATEGORIES}

        events_repo = EventRepository(session)
        events = []
        for title, days, hour, loc_idx, cat_names, price in EVENTS:
            events.append(
                await events_repo.create(
                    title=title,
                    event_date=(now + timedelta(days=days)).replace(hour=hour),
                    location_id=locations[loc_idx].id,
                    organizer_id=users[ORGANIZER_BY_LOCATION[loc_idx]].id,
                    categories=[categories[c] for c in cat_names],
                    price=price,
                )
            )

        bookings_repo = BookingRepository(session)
        for email, event_idx, status, comment in BOOKINGS:
            await bookings_repo.create(
                user_id=users[email].id, event_id=events[event_idx].id, status=status, comment=comment
            )

        for requester, addressee, status in FRIENDSHIPS:
            session.add(
                Friendship(requester_id=users[requester].id, addressee_id=users[addressee].id, status=status)
            )

        for inviter, invitee, event_idx, message in INVITATIONS:
            session.add(
                EventInvitation(
                    event_id=events[event_idx].id,
                    inviter_id=users[inviter].id,
                    invitee_id=users[invitee].id,
                    message=message,
                )
            )

        for email, event_idx, scores, comment in FEEDBACK:
            session.add(
                EventFeedback(
                    event_id=events[event_idx].id,
                    user_id=users[email].id,
                    comment=comment,
                    scores=[FeedbackScore(criterion=c, positive=v) for c, v in scores.items()],
                )
            )

        await session.commit()

    print(
        f"Тестовые данные загружены: пользователей {len(USERS)}, площадок {len(LOCATIONS)}, "
        f"категорий {len(CATEGORIES)}, мероприятий {len(EVENTS)}, броней {len(BOOKINGS)}, "
        f"дружб {len(FRIENDSHIPS)}, приглашений {len(INVITATIONS)}, "
        f"отзывов {len(FEEDBACK)}."
    )
    print(f"Пароль всех пользователей: {DEFAULT_PASSWORD}")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
