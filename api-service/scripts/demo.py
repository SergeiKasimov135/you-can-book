"""Тестовый скрипт ЛР1: демонстрирует работу с БД во всех сценариях приложения.

Запуск (из папки api-service):
    python -m scripts.demo          # результаты запросов в консоль
    python -m scripts.demo --sql    # плюс все SQL-запросы, которые генерирует SQLAlchemy

Перед началом скрипт перезагружает тестовые данные (scripts/seed.py),
поэтому его можно запускать повторно с одинаковым результатом.
"""
import argparse
import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from app.db import SessionFactory, engine
from app.models import Booking, BookingStatus, Category, Event, Location, User, event_categories
from app.services import (
    BookingService,
    CatalogService,
    ServiceError,
    UserService,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from scripts.seed import DEFAULT_PASSWORD, LOCAL_TZ, seed

# ---------------------------------------------------------------- вывод в консоль


def header(title: str) -> None:
    print(f"\n{'=' * 78}\n {title}\n{'=' * 78}")


def step(title: str) -> None:
    print(f"\n--- {title}")


def ok(message: str) -> None:
    print(f"  [OK]   {message}")


def fail(message: str) -> None:
    print(f"  [ОТКАЗ] {message}")


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    rows = [["" if v is None else str(v) for v in row] for row in rows]
    if not rows:
        print("  (пусто)")
        return
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    line = "  " + " | ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  " + "-+-".join("-" * w for w in widths))
    for r in rows:
        print("  " + " | ".join(v.ljust(w) for v, w in zip(r, widths)))


def fmt_dt(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")


def print_events(events: Sequence[Event]) -> None:
    table(
        ["id", "Мероприятие", "Дата", "Площадка", "Категории", "Цена", "Статус"],
        [
            (
                e.id,
                e.title,
                fmt_dt(e.event_date),
                e.location.name,
                ", ".join(c.name for c in e.categories),
                e.price if e.price is not None else "бесплатно",
                e.status.value,
            )
            for e in events
        ],
    )


def print_bookings(bookings: Sequence[Booking]) -> None:
    table(
        ["Бронь", "Клиент", "Мероприятие", "Дата", "Статус", "Комментарий"],
        [
            (b.id, b.user.email, b.event.title, fmt_dt(b.event.event_date), b.status.value, b.comment)
            for b in bookings
        ],
    )


async def expect_error(action: Callable[[], Awaitable[object]]) -> None:
    """Выполняет действие, которое ДОЛЖНО быть отклонено, и печатает причину."""
    try:
        await action()
    except ServiceError as exc:
        fail(f"{type(exc).__name__}: {exc}")
        if isinstance(exc.__cause__, IntegrityError):  # ошибку обнаружила сама БД
            print(f"           PostgreSQL: {str(exc.__cause__.orig).splitlines()[0]}")
    else:
        raise AssertionError("Ожидалась ошибка, но действие выполнилось")


# ---------------------------------------------------------------- сценарии


async def scenario_connection() -> None:
    header("0. Подключение к PostgreSQL")
    async with SessionFactory() as session:
        version = await session.scalar(text("SELECT version()"))
        database = await session.scalar(text("SELECT current_database()"))
        ok(f"Подключено к базе «{database}»")
        print(f"  {version}")

        step("Количество записей в таблицах после загрузки тестовых данных")
        rows = []
        for model in (User, Location, Category, Event, Booking):
            rows.append((model.__tablename__, await session.scalar(select(func.count()).select_from(model))))
        rows.append(
            ("event_categories", await session.scalar(select(func.count()).select_from(event_categories)))
        )
        table(["Таблица", "Строк"], rows)


async def scenario_users() -> int:
    header("1. Пользователи: регистрация и вход (роль CLIENT)")
    async with SessionFactory() as session:
        users = UserService(session)

        step("Регистрация нового клиента")
        maria = await users.register("Maria@ycb.ru", "secret-pass", "Мария Иванова")
        ok(f"Создан пользователь id={maria.id}, email={maria.email}, роль={maria.role.value}")
        print(f"  В БД хранится только хеш пароля: {maria.hashed_password[:29]}...")

        step("Повторная регистрация с тем же email")
        await expect_error(lambda: users.register("maria@ycb.ru", "other", "Двойник"))

        step("Вход: верный и неверный пароль")
        user = await users.authenticate("maria@ycb.ru", "secret-pass")
        ok(f"Верный пароль -> пользователь id={user.id}")
        bad = await users.authenticate("maria@ycb.ru", "wrong")
        fail(f"Неверный пароль -> {bad}")

        step("Редактирование профиля")
        maria = await users.update_profile(maria.id, "Мария Сергеевна Иванова")
        ok(f"Новое имя: {maria.full_name}")

        step("Список всех пользователей")
        table(
            ["id", "Email", "ФИО", "Роль"],
            [(u.id, u.email, u.full_name, u.role.value) for u in await users.list()],
        )
        return maria.id


async def scenario_catalog() -> None:
    header("2. Клиент: просмотр каталога мероприятий с фильтрами")
    async with SessionFactory() as session:
        catalog = CatalogService(session)
        categories = {c.name: c.id for c in await catalog.list_categories()}

        step("Весь каталог: будущие запланированные мероприятия, по дате")
        print_events(await catalog.list_catalog())

        step("Включая прошедшие (include_past=True)")
        print_events(await catalog.list_catalog(include_past=True))

        step("Фильтр: категория «Концерты»")
        print_events(await catalog.list_catalog(category_id=categories["Концерты"]))

        step("Фильтр: ближайшие 7 дней")
        now = datetime.now(LOCAL_TZ)
        print_events(await catalog.list_catalog(date_from=now, date_to=now + timedelta(days=7)))

        step("Фильтр: площадка id=2 (лекторий)")
        print_events(await catalog.list_catalog(location_id=2))


async def scenario_booking(maria_id: int) -> None:
    header("3. Клиент: бронирование места (оплата на месте)")
    async with SessionFactory() as session:
        bookings = BookingService(session)

        step("Мария бронирует «Джазовый вечер» (id=1)")
        b = await bookings.book(maria_id, 1, comment="Первый раз у вас")
        ok(f"Бронь №{b.id}: «{b.event.title}», статус {b.status.value}")

        step("Повторная бронь того же мероприятия — проверка в сервисе")
        await expect_error(lambda: bookings.book(maria_id, 1))

        step("То же самое в обход сервиса: прямой INSERT — срабатывает индекс ux_bookings_active")
        try:
            session.add(Booking(user_id=maria_id, event_id=1))
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            fail(f"PostgreSQL: {str(exc.orig).splitlines()[0]}")

        step("Бронь прошедшего мероприятия (id=10)")
        await expect_error(lambda: bookings.book(maria_id, 10))

        step("Мария бронирует ещё лекцию и спектакль")
        await bookings.book(maria_id, 4)
        await bookings.book(maria_id, 5)

        step("Мои брони (Мария)")
        print_bookings(await bookings.list_my(maria_id))


async def scenario_cancel_booking(maria_id: int) -> None:
    header("4. Клиент: отмена брони и повторное бронирование")
    async with SessionFactory() as session:
        users = UserService(session)
        bookings = BookingService(session)
        maria = await users.get(maria_id)
        ivan = await users.get(2)

        maria_booking = next(b for b in await bookings.list_my(maria_id) if b.event_id == 5)

        step(f"Иван пытается отменить чужую бронь №{maria_booking.id}")
        await expect_error(lambda: bookings.cancel(maria_booking.id, actor=ivan))

        step(f"Мария отменяет свою бронь №{maria_booking.id}")
        cancelled = await bookings.cancel(maria_booking.id, actor=maria)
        ok(f"Бронь №{cancelled.id} -> {cancelled.status.value}")

        step("Повторная отмена той же брони")
        await expect_error(lambda: bookings.cancel(maria_booking.id, actor=maria))

        step("Мария снова бронирует тот же спектакль — индекс учитывает только активные брони")
        again = await bookings.book(maria_id, 5, comment="Всё-таки пойду")
        ok(f"Новая бронь №{again.id}, статус {again.status.value}")

        print_bookings(await bookings.list_my(maria_id))


async def scenario_recommendations() -> None:
    header("5. Данные для рекомендаций (будут переданы по gRPC в ЛР3)")
    async with SessionFactory() as session:
        bookings = BookingService(session)
        for user_id, name in ((2, "Иван"), (3, "Ольга")):
            data = await bookings.recommendation_input(user_id)
            step(f"{name}: интересы по категориям (ATTENDED = 2, BOOKED = 1)")
            table(["Категория", "Вес"], [(n, w) for _, n, w in data.history])
            step(f"{name}: кандидаты — будущие мероприятия без активной брони")
            table(
                ["id", "Мероприятие", "Категории"],
                [(e.id, e.title, ", ".join(c.name for c in e.categories)) for e in data.candidates],
            )


async def scenario_admin_catalog() -> int:
    header("6. Администратор: CRUD площадок, категорий и мероприятий")
    async with SessionFactory() as session:
        catalog = CatalogService(session)

        step("Создать площадку")
        loc = await catalog.create_location("Арт-кафе «Чердак»", "г. Самара, ул. Чапаевская, 20", 60)
        ok(f"Площадка id={loc.id}: {loc.name}, вместимость {loc.capacity}")

        step("Изменить площадку")
        loc = await catalog.update_location(loc.id, capacity=80, address="г. Самара, ул. Чапаевская, 22")
        ok(f"Площадка id={loc.id}: {loc.address}, вместимость {loc.capacity}")

        step("Создать категорию и переименовать её")
        cat = await catalog.create_category("Квизы")
        cat = await catalog.rename_category(cat.id, "Квизы и игры")
        ok(f"Категория id={cat.id}: {cat.name}")

        step("Категория с существующим названием")
        await expect_error(lambda: catalog.create_category("Концерты"))

        step("Создать мероприятие с двумя категориями (M:N event_categories)")
        event = await catalog.create_event(
            title="Музыкальный квиз",
            event_date=datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)
            + timedelta(days=9),
            location_id=loc.id,
            category_ids=[cat.id, 1],
            price=Decimal("500.00"),
            description="Угадай мелодию командами по 4 человека",
        )
        print_events([event])

        step("Мероприятие без категорий (кратность 1..* проверяется в коде)")
        await expect_error(
            lambda: catalog.create_event(
                title="Без категорий",
                event_date=event.event_date,
                location_id=loc.id,
                category_ids=[],
            )
        )

        step("Изменить описание и категории — уведомлять никого не нужно")
        change = await catalog.update_event(event.id, description="Командная игра", category_ids=[cat.id])
        ok(f"Изменены поля: {list(change.changes)}, получатели уведомления: {change.recipients}")
        print_events([change.event])
        return event.id


async def scenario_admin_reschedule_and_cancel() -> None:
    header("7. Администратор: перенос и отмена мероприятия")
    async with SessionFactory() as session:
        catalog = CatalogService(session)
        bookings = BookingService(session)

        event = await catalog.get_event(1)
        new_date = event.event_date + timedelta(days=2)
        step(f"Перенос «{event.title}» на {fmt_dt(new_date)}")
        change = await catalog.update_event(1, event_date=new_date)
        ok(f"Изменено: event_date -> {fmt_dt(change.event.event_date)}")
        ok(f"Кому отправить уведомление (user_id): {change.recipients}")

        step("Отмена спектакля «Вишнёвый сад» (id=5)")
        print_bookings(await bookings.list_for_admin(event_id=5))
        change = await catalog.cancel_event(5)
        ok(f"Статус мероприятия: {change.event.status.value}")
        ok(f"Брони отменены одним UPDATE ... RETURNING, уведомить: {change.recipients}")
        print_bookings(await bookings.list_for_admin(event_id=5))

        step("Бронь на отменённое мероприятие")
        await expect_error(lambda: bookings.book(4, 5))

        step("Каталог по умолчанию не показывает отменённые мероприятия")
        titles = [e.title for e in await catalog.list_catalog()]
        ok(f"«Вишнёвый сад» в каталоге: {'Спектакль «Вишнёвый сад»' in titles}")


async def scenario_admin_bookings() -> None:
    header("8. Администратор: брони любого клиента, отметка посещения")
    async with SessionFactory() as session:
        bookings = BookingService(session)

        step("Все брони клиента Ивана (user_id=2)")
        print_bookings(await bookings.list_for_admin(user_id=2))

        step("Все активные брони в системе")
        print_bookings(await bookings.list_for_admin(status=BookingStatus.BOOKED))

        step("Отметить посещение: бронь №7 (Павел, стендап)")
        b = await bookings.mark_attended(7)
        ok(f"Бронь №{b.id} -> {b.status.value}")

        step("Отметить посещение отменённой брони №8")
        await expect_error(lambda: bookings.mark_attended(8))


async def scenario_deletes(maria_id: int, quiz_event_id: int) -> None:
    header("9. Удаление данных и ссылочная целостность")
    async with SessionFactory() as session:
        catalog = CatalogService(session)
        users = UserService(session)

        step("Удалить мероприятие, на которое есть брони (FK ... ON DELETE RESTRICT)")
        await expect_error(lambda: catalog.delete_event(1))

        step("Удалить площадку, на которой есть мероприятия (FK ... ON DELETE RESTRICT)")
        await expect_error(lambda: catalog.delete_location(1))

        step(f"Удалить мероприятие без броней (id={quiz_event_id}), связи удалит БД каскадно")
        await catalog.delete_event(quiz_event_id)
        ok("Мероприятие удалено")

        step("Удалить категорию «Квизы и игры» (теперь без мероприятий)")
        quiz = next(c for c in await catalog.list_categories() if c.name == "Квизы и игры")
        await catalog.delete_category(quiz.id)
        ok("Категория удалена")

        step("Удалить пустую площадку «Чердак»")
        loc = next(x for x in await catalog.list_locations() if "Чердак" in x.name)
        await catalog.delete_location(loc.id)
        ok("Площадка удалена")

        step("Удалить пользователя Марию — её брони удалятся каскадно (ON DELETE CASCADE)")
        before = await session.scalar(select(func.count()).where(Booking.user_id == maria_id))
        await users.delete(maria_id)
        after = await session.scalar(select(func.count()).where(Booking.user_id == maria_id))
        ok(f"Броней Марии: было {before}, стало {after}")


async def scenario_summary() -> None:
    header("Итог: состояние таблиц")
    async with SessionFactory() as session:
        rows = []
        for model in (User, Location, Category, Event, Booking):
            rows.append((model.__tablename__, await session.scalar(select(func.count()).select_from(model))))
        table(["Таблица", "Строк"], rows)
        step("Брони по статусам")
        result = await session.execute(
            select(Booking.status, func.count()).group_by(Booking.status).order_by(Booking.status)
        )
        table(["Статус", "Количество"], [(s.value, n) for s, n in result])


async def main(show_sql: bool) -> None:
    engine.echo = show_sql
    try:
        await seed()
        print(f"(вход для всех тестовых пользователей: пароль {DEFAULT_PASSWORD})")
        await scenario_connection()
        maria_id = await scenario_users()
        await scenario_catalog()
        await scenario_booking(maria_id)
        await scenario_cancel_booking(maria_id)
        await scenario_recommendations()
        quiz_event_id = await scenario_admin_catalog()
        await scenario_admin_reschedule_and_cancel()
        await scenario_admin_bookings()
        await scenario_deletes(maria_id, quiz_event_id)
        await scenario_summary()
        print("\nВсе сценарии выполнены.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Демонстрация работы с БД (ЛР1)")
    parser.add_argument("--sql", action="store_true", help="печатать SQL-запросы SQLAlchemy")
    asyncio.run(main(parser.parse_args().sql))
