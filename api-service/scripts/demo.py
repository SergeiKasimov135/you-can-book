import argparse
import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from app.db import SessionFactory, engine
from app.models import (
    Booking,
    BookingStatus,
    Category,
    Event,
    EventFeedback,
    EventInvitation,
    CRITERION_QUESTIONS,
    FeedbackCriterion,
    FeedbackScore,
    Friendship,
    Location,
    User,
    UserRole,
    event_categories,
)
from app.services import (
    BookingService,
    CatalogService,
    FeedbackService,
    FriendService,
    ServiceError,
    UserService,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from scripts.seed import DEFAULT_PASSWORD, LOCAL_TZ, seed

# id тестовых пользователей из scripts/seed.py
ADMIN, IVAN, OLGA, PAVEL, DMITRY, ANNA = 1, 2, 3, 4, 5, 6
TABLES = (
    User, Location, Category, Event, Booking, Friendship, EventInvitation,
    EventFeedback, FeedbackScore,
)

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
        ["id", "Мероприятие", "Дата", "Площадка", "Категории", "Цена", "Статус", "Организатор"],
        [
            (
                e.id,
                e.title,
                fmt_dt(e.event_date),
                e.location.name,
                ", ".join(c.name for c in e.categories),
                e.price if e.price is not None else "бесплатно",
                e.status.value,
                e.organizer.email if e.organizer else "",
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
    # Действие должно быть отклонено — печатаем причину
    try:
        await action()
    except ServiceError as exc:
        fail(f"{type(exc).__name__}: {exc}")
        if isinstance(exc.__cause__, IntegrityError):  # ошибку обнаружила сама БД
            print(f"           PostgreSQL: {str(exc.__cause__.orig).splitlines()[0]}")
    else:
        raise AssertionError("Ожидалась ошибка, но действие выполнилось")


async def direct_insert(obj: object) -> None:
    # INSERT в обход сервисов: ограничение проверяет БД
    async with SessionFactory() as session:
        try:
            session.add(obj)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            fail(f"PostgreSQL: {str(exc.orig).splitlines()[0]}")
        else:
            raise AssertionError("Ожидалась ошибка БД, но INSERT выполнился")


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
        for model in TABLES:
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
        await direct_insert(Booking(user_id=maria_id, event_id=1))

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


async def scenario_admin_catalog() -> int:
    header("5. Администратор и организатор: площадки, категории, мероприятия")
    async with SessionFactory() as session:
        catalog = CatalogService(session)
        users = UserService(session)
        admin, dmitry, anna, ivan = [await users.get(i) for i in (ADMIN, DMITRY, ANNA, IVAN)]

        step("Администратор создаёт площадку")
        loc = await catalog.create_location(admin, "Арт-кафе «Чердак»", "г. Самара, ул. Чапаевская, 20", 60)
        ok(f"Площадка id={loc.id}: {loc.name}, вместимость {loc.capacity}")

        step("Администратор изменяет площадку")
        loc = await catalog.update_location(
            loc.id, admin, capacity=80, address="г. Самара, ул. Чапаевская, 22"
        )
        ok(f"Площадка id={loc.id}: {loc.address}, вместимость {loc.capacity}")

        step("Организатор пытается создать площадку — это право только администратора")
        await expect_error(lambda: catalog.create_location(dmitry, "Своя площадка", "где-то", 10))

        step("Администратор создаёт категорию и переименовывает её")
        cat = await catalog.create_category(admin, "Квизы")
        cat = await catalog.rename_category(cat.id, admin, "Квизы и игры")
        ok(f"Категория id={cat.id}: {cat.name}")

        step("Категория с существующим названием")
        await expect_error(lambda: catalog.create_category(admin, "Концерты"))

        step("Клиент Иван пытается создать мероприятие")
        await expect_error(
            lambda: catalog.create_event(
                ivan,
                title="Квартирник",
                event_date=datetime.now(LOCAL_TZ) + timedelta(days=3),
                location_id=loc.id,
                category_ids=[1],
            )
        )

        step("Организатор Дмитрий создаёт мероприятие с двумя категориями (M:N event_categories)")
        event = await catalog.create_event(
            dmitry,
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
                dmitry,
                title="Без категорий",
                event_date=event.event_date,
                location_id=loc.id,
                category_ids=[],
            )
        )

        step("Организатор Анна пытается изменить чужое мероприятие")
        await expect_error(lambda: catalog.update_event(event.id, anna, description="Моё!"))

        step("Дмитрий меняет описание и категории — уведомлять никого не нужно")
        change = await catalog.update_event(
            event.id, dmitry, description="Командная игра", category_ids=[cat.id]
        )
        ok(f"Изменены поля: {list(change.changes)}, получатели уведомления: {change.recipients}")
        print_events([change.event])

        step("Мероприятия организатора Дмитрия (включая прошедшие)")
        print_events(await catalog.list_my_events(dmitry))

        step("Администратор назначает клиента Павла организатором")
        pavel = await users.change_role(PAVEL, UserRole.ORGANIZER, admin)
        ok(f"{pavel.email}: роль {pavel.role.value}")
        step("Организатор Дмитрий пытается назначать роли")
        await expect_error(lambda: users.change_role(IVAN, UserRole.ADMIN, dmitry))
        await users.change_role(PAVEL, UserRole.CLIENT, admin)  # возвращаем как было
        return event.id


async def scenario_admin_reschedule_and_cancel() -> None:
    header("6. Организатор: перенос и отмена своего мероприятия")
    async with SessionFactory() as session:
        catalog = CatalogService(session)
        bookings = BookingService(session)
        users = UserService(session)
        dmitry, anna = await users.get(DMITRY), await users.get(ANNA)

        event = await catalog.get_event(1)
        new_date = event.event_date + timedelta(days=2)
        step(f"Дмитрий переносит «{event.title}» на {fmt_dt(new_date)}")
        change = await catalog.update_event(1, dmitry, event_date=new_date)
        ok(f"Изменено: event_date -> {fmt_dt(change.event.event_date)}")
        ok(f"Кому отправить уведомление (user_id): {change.recipients}")

        step("Анна (организатор лекций) пытается отменить спектакль Дмитрия")
        await expect_error(lambda: catalog.cancel_event(5, anna))

        step("Дмитрий отменяет спектакль «Вишнёвый сад» (id=5)")
        print_bookings(await bookings.list_for_event(5, dmitry))
        change = await catalog.cancel_event(5, dmitry)
        ok(f"Статус мероприятия: {change.event.status.value}")
        ok(f"Брони отменены одним UPDATE ... RETURNING, уведомить: {change.recipients}")
        print_bookings(await bookings.list_for_event(5, dmitry))

        step("Бронь на отменённое мероприятие")
        await expect_error(lambda: bookings.book(4, 5))

        step("Каталог по умолчанию не показывает отменённые мероприятия")
        titles = [e.title for e in await catalog.list_catalog()]
        ok(f"«Вишнёвый сад» в каталоге: {'Спектакль «Вишнёвый сад»' in titles}")


async def scenario_admin_bookings() -> None:
    header("7. Администратор и организатор: брони, отметка посещения")
    async with SessionFactory() as session:
        bookings = BookingService(session)
        users = UserService(session)
        dmitry, anna = await users.get(DMITRY), await users.get(ANNA)

        step("Все брони клиента Ивана (user_id=2)")
        print_bookings(await bookings.list_for_admin(user_id=2))

        step("Все активные брони в системе")
        print_bookings(await bookings.list_for_admin(status=BookingStatus.BOOKED))

        step("Анна пытается отметить посещение на чужом мероприятии (бронь №7, стендап Дмитрия)")
        await expect_error(lambda: bookings.mark_attended(7, anna))

        step("Дмитрий отмечает посещение: бронь №7 (Павел, стендап)")
        b = await bookings.mark_attended(7, dmitry)
        ok(f"Бронь №{b.id} -> {b.status.value}")

        step("Отметить посещение отменённой брони №8")
        await expect_error(lambda: bookings.mark_attended(8, dmitry))


def print_feedback(items: Sequence[EventFeedback]) -> None:
    table(
        ["Отзыв", "Автор", "Отметки (+ хорошо, - плохо)", "Комментарий"],
        [
            (
                f.id,
                f.user.email,
                ", ".join(f"{CRITERION_QUESTIONS[sc.criterion][0]} {'+' if sc.positive else '-'}" for sc in f.scores),
                f.comment,
            )
            for f in items
        ],
    )


async def print_rating(feedback: FeedbackService, event_id: int, title: str) -> None:
    rating = await feedback.rating(event_id)
    step(
        f"Рейтинг «{title}»: отзывов {rating.feedback_count}, "
        f"отметок «хорошо» {rating.positive} из {rating.total}, доля {rating.overall}"
    )
    table(
        ["Критерий", "Хорошо", "Отметили", "Доля хороших"],
        [(s.title, s.positive, s.total, s.share) for s in rating.by_criterion],
    )


async def scenario_friends(maria_id: int) -> None:
    header("8. Друзья: заявки, список друзей, приглашения на мероприятия")
    async with SessionFactory() as session:
        users = UserService(session)
        friends = FriendService(session)
        ivan, olga, pavel, maria = [await users.get(i) for i in (IVAN, OLGA, PAVEL, maria_id)]

        def names(items: Sequence[User]) -> str:
            return ", ".join(u.full_name for u in items) or "(никого)"

        step("Друзья Ивана и его входящие заявки")
        ok(f"Друзья: {names(await friends.list_friends(IVAN))}")
        incoming = await friends.list_incoming_requests(IVAN)
        table(["Заявка", "От кого"], [(r.id, r.requester.full_name) for r in incoming])

        step("Иван принимает заявку Павла")
        await friends.accept_request(incoming[0].id, ivan)
        ok(f"Друзья Ивана: {names(await friends.list_friends(IVAN))}")

        step("Мария отправляет заявку Ивану, Иван отклоняет (строка заявки удаляется)")
        request = await friends.send_request(maria, IVAN)
        ok(f"Заявка №{request.id}: {request.status.value}")
        await friends.decline_request(request.id, ivan)
        ok(f"Друзья Ивана: {names(await friends.list_friends(IVAN))}")

        step("Ошибки: заявка самому себе, повторная заявка другу, ответ на чужую заявку")
        await expect_error(lambda: friends.send_request(ivan, IVAN))
        await expect_error(lambda: friends.send_request(olga, IVAN))
        request = await friends.send_request(maria, PAVEL)
        await expect_error(lambda: friends.accept_request(request.id, ivan))

        step("Прямой INSERT встречной строки (Ольга -> Иван) — индекс ux_friendships_pair")
        await direct_insert(Friendship(requester_id=OLGA, addressee_id=IVAN))

        step("Павел смотрит, кто из друзей идёт на «Джазовый вечер» (id=1)")
        ok(f"Идут: {names(await friends.friends_going(PAVEL, 1))}")

        step("Приглашения Ивана: Ольга зовёт на лекцию")
        invitations = await friends.list_invitations(IVAN)
        table(
            ["№", "От кого", "Мероприятие", "Сообщение", "Статус"],
            [(i.id, i.inviter.full_name, i.event.title, i.message, i.status.value) for i in invitations],
        )

        step("Иван принимает приглашение — бронь создаётся в той же транзакции")
        invitation, booking = await friends.respond(invitations[0].id, ivan, accept=True)
        ok(f"Приглашение №{invitation.id}: {invitation.status.value}; бронь №{booking.id}: {booking.comment}")
        await expect_error(lambda: friends.respond(invitation.id, ivan, accept=False))

        step("Иван зовёт Павла на «Джазовый вечер», Павел отказывается")
        invitation = await friends.invite(ivan, PAVEL, 1, "Пойдём вместе? Ольга тоже идёт")
        ok(f"Приглашение №{invitation.id} -> {invitation.invitee.full_name}")
        invitation, booking = await friends.respond(invitation.id, pavel, accept=False)
        ok(f"Приглашение №{invitation.id}: {invitation.status.value}, бронь: {booking}")

        step("Ошибки: повторное приглашение, приглашение не-друга, друг уже записан, прошедшее")
        await expect_error(lambda: friends.invite(ivan, PAVEL, 1))
        await expect_error(lambda: friends.invite(ivan, maria_id, 1))
        await expect_error(lambda: friends.invite(ivan, OLGA, 1))
        await expect_error(lambda: friends.invite(ivan, OLGA, 10))


async def scenario_feedback() -> None:
    header("9. Отзывы: отметки «хорошо / плохо» по критериям (как теги в такси)")
    async with SessionFactory() as session:
        users = UserService(session)
        feedback = FeedbackService(session)
        ivan, pavel = [await users.get(i) for i in (IVAN, PAVEL)]
        C = FeedbackCriterion

        step("Критерии — фиксированный enum: пользователь выбирает из списка, у каждого есть вопрос")
        table(
            ["Код (в БД)", "Критерий", "Вопрос"],
            [(code.value, title, question) for code, title, question in feedback.list_criteria()],
        )

        step("Отзывы о прошедшем «Рок-концерте «Осень»» (id=10): отмечены не все критерии")
        print_feedback(await feedback.list_for_event(10))
        await print_rating(feedback, 10, "Рок-концерт «Осень»")

        step("Павел (посетил лекцию id=11) отмечает только 3 критерия из 5, остальные пропускает")
        fb = await feedback.leave_feedback(
            pavel,
            11,
            {C.CULTURE: True, C.ORGANIZATION: True, C.VENUE: False},
            comment="В зале было душно",
        )
        print_feedback([fb])
        await print_rating(feedback, 11, "Лекция «Нейросети без формул»")

        step("Ошибки: повторный отзыв, без посещения, пустой отзыв, критерий не из списка, не булево значение")
        await expect_error(lambda: feedback.leave_feedback(pavel, 11, {C.AUDIENCE: True}))
        await expect_error(lambda: feedback.leave_feedback(ivan, 11, {C.AUDIENCE: True}))
        await expect_error(lambda: feedback.leave_feedback(ivan, 10, {}))
        await expect_error(lambda: feedback.leave_feedback(pavel, 6, {"Еда": True}))
        await expect_error(lambda: feedback.leave_feedback(pavel, 6, {C.AUDIENCE: 0.9}))
        olga_fb = next(f for f in await feedback.list_for_event(10) if f.user_id == OLGA)

        step("Прямой INSERT второй отметки по тому же критерию — составной PK pk_feedback_scores")
        await direct_insert(
            FeedbackScore(feedback_id=olga_fb.id, criterion=C.AUDIENCE, positive=False)
        )

        step("Прямой INSERT с кодом вне enum — CHECK ck_feedback_scores_criterion")
        async with SessionFactory() as raw:
            try:
                await raw.execute(
                    text("INSERT INTO feedback_scores (feedback_id, criterion, positive) VALUES (:f, 'FOOD', true)"),
                    {"f": olga_fb.id},
                )
                await raw.commit()
            except IntegrityError as exc:
                await raw.rollback()
                fail(f"PostgreSQL: {str(exc.orig).splitlines()[0]}")
            else:
                raise AssertionError("Ожидалась ошибка БД, но INSERT выполнился")


async def scenario_deletes(quiz_event_id: int) -> None:
    header("10. Удаление данных и ссылочная целостность")
    async with SessionFactory() as session:
        catalog = CatalogService(session)
        users = UserService(session)
        admin, dmitry = await users.get(ADMIN), await users.get(DMITRY)

        step("Удалить мероприятие, на которое есть брони (FK ... ON DELETE RESTRICT)")
        await expect_error(lambda: catalog.delete_event(1, dmitry))

        step("Удалить площадку, на которой есть мероприятия (FK ... ON DELETE RESTRICT)")
        await expect_error(lambda: catalog.delete_location(1, admin))

        step(f"Дмитрий удаляет своё мероприятие без броней (id={quiz_event_id}), связи удалит БД")
        await catalog.delete_event(quiz_event_id, dmitry)
        ok("Мероприятие удалено")

        step("Удалить категорию «Квизы и игры» (теперь без мероприятий)")
        quiz = next(c for c in await catalog.list_categories() if c.name == "Квизы и игры")
        await catalog.delete_category(quiz.id, admin)
        ok("Категория удалена")

        step("Удалить пустую площадку «Чердак»")
        loc = next(x for x in await catalog.list_locations() if "Чердак" in x.name)
        await catalog.delete_location(loc.id, admin)
        ok("Площадка удалена")

        step("Удалить пользователя Ивана — его брони, дружбы и отзывы удалит БД (ON DELETE CASCADE)")

        async def ivan_rows() -> list[int]:
            return [
                await session.scalar(select(func.count()).where(Booking.user_id == IVAN)),
                await session.scalar(
                    select(func.count()).where(
                        (Friendship.requester_id == IVAN) | (Friendship.addressee_id == IVAN)
                    )
                ),
                await session.scalar(select(func.count()).where(EventFeedback.user_id == IVAN)),
            ]

        before = await ivan_rows()
        await users.delete(IVAN)
        after = await ivan_rows()
        table(
            ["Связанные строки", "Было", "Стало"],
            [(n, b, a) for n, b, a in zip(("брони", "дружбы", "отзывы"), before, after)],
        )

        step("Удалить организатора Анну — её мероприятия остаются без организатора (ON DELETE SET NULL)")
        await users.delete(ANNA)
        orphan = await session.scalar(
            select(func.count()).select_from(Event).where(Event.organizer_id.is_(None))
        )
        ok(f"Мероприятий без организатора: {orphan}")


async def scenario_summary() -> None:
    header("Итог: состояние таблиц")
    async with SessionFactory() as session:
        rows = []
        for model in TABLES:
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
        quiz_event_id = await scenario_admin_catalog()
        await scenario_admin_reschedule_and_cancel()
        await scenario_admin_bookings()
        await scenario_friends(maria_id)
        await scenario_feedback()
        await scenario_deletes(quiz_event_id)
        await scenario_summary()
        print("\nВсе сценарии выполнены.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Демонстрация работы с БД (ЛР1)")
    parser.add_argument("--sql", action="store_true", help="печатать SQL-запросы SQLAlchemy")
    asyncio.run(main(parser.parse_args().sql))
