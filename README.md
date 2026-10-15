# You Can Book

Распределённое приложение агентства досуга: каталог городских мероприятий и бронирование мест (оплата на месте).

Текущее состояние: **ЛР1** — база данных PostgreSQL в Docker, модели SQLAlchemy, CRUD, миграции Alembic, тестовые данные и демонстрационный скрипт.

---

## Быстрый старт (одна команда)

Из корня проекта в PowerShell (Docker Desktop должен быть запущен):

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Скрипт `setup.ps1` по шагам:

1. Проверяет, что Docker запущен.
2. Создаёт `.env` и `api-service\.env` из `.env.example`, если их нет. Порт в строке подключения подгоняется под `POSTGRES_PORT`.
3. Поднимает PostgreSQL. Если контейнер был создан со старым портом, пересоздаёт его. Затем ждёт статуса `healthy`.
4. Создаёт `.venv`, ставит зависимости, применяет миграции, загружает тестовые данные и запускает демо.
5. Если подключиться к базе с Windows не удалось (VPN, занятый порт), автоматически повторяет шаг 4 **внутри Docker**.

Флаги:
- `-InDocker` — сразу запускать код в Docker, без `.venv`.
- `-SkipDemo` — только миграции и тестовые данные.

Ниже те же шаги описаны вручную — их нужно понимать для защиты.

---

## Работа в PyCharm

### Один раз: настроить проект

1. Открой в PyCharm папку `you-can-book` (корень, не `api-service`).
2. **Интерпретатор.** `Ctrl+Alt+S` → *Project: you-can-book* → *Python Interpreter* → шестерёнка / *Add Interpreter* → *Add Local Interpreter* → *Virtualenv Environment* → **Existing** → путь:
   ```
   <папка проекта>\api-service\.venv\Scripts\python.exe
   ```
   Проверка: в списке пакетов видны `SQLAlchemy`, `alembic`, `asyncpg`, `pydantic-settings`, `bcrypt`.
   Если `api-service\.venv` ещё нет, сначала выполни `.\setup.ps1`: скрипт его создаст.
3. Убедись, что папка `api-service` синяя (*Sources Root*), а `.venv` — оранжевая (*Excluded*). Если нет: правой кнопкой → *Mark Directory as*.

После этого исчезнут подчёркивания `Unresolved reference`. Если остались — *File* → *Invalidate Caches…* → *Invalidate and Restart*.

### Запуск из PyCharm

В выпадающем списке конфигураций (вверху справа, рядом с зелёной кнопкой ▶) есть готовые конфигурации. Они запускаются из папки `api-service` с выбранным интерпретатором проекта:

| Конфигурация | Что выполняет |
| --- | --- |
| `1. Alembic upgrade head` | `python -m alembic upgrade head` — создать таблицы |
| `2. Seed test data` | `python -m scripts.seed` — тестовые данные |
| `3. Demo` | `python -m scripts.demo` — все сценарии ЛР1 |
| `3. Demo (with SQL)` | то же + SQL-запросы, которые генерирует SQLAlchemy |
| `Alembic current` | текущая версия схемы БД |

Перед запуском контейнер с PostgreSQL должен работать: `docker compose up -d` в терминале PyCharm (*Alt+F12*) из корня проекта.

Если конфигурации не появились, перезапусти PyCharm: они лежат в папке `.run` в корне проекта (и попадают в git).

---

## Роли и возможности

| Роль | Кто это | Что может |
| --- | --- | --- |
| `CLIENT` | посетитель | каталог, бронирование, друзья и приглашения, отзывы о посещённых мероприятиях |
| `ORGANIZER` | администратор мероприятий | всё, что клиент, плюс создаёт мероприятия и управляет **только своими**: изменение, перенос, отмена, удаление, список гостей, отметка посещения |
| `ADMIN` | администратор агентства | всё: площадки, категории, любые мероприятия, назначение ролей |

Проверки прав собраны в `app/services/permissions.py`. Организатор мероприятия хранится в `events.organizer_id`.

**Друзья.** Пользователь отправляет заявку (`friendships`, статус `PENDING`), второй принимает её (`ACCEPTED`) или отклоняет (строка удаляется). На одну пару пользователей в таблице может быть только одна строка в любом направлении: это обеспечивает уникальный индекс по выражению `ux_friendships_pair` на `(least(requester_id, addressee_id), greatest(...))`. Друга можно пригласить на мероприятие (`event_invitations`). Если друг принимает приглашение, бронь для него создаётся в той же транзакции. Можно также посмотреть, кто из друзей уже идёт на мероприятие.

**Отзывы.** Оставить отзыв может только посетитель (у него есть бронь в статусе `ATTENDED`), один отзыв на мероприятие. Отзыв работает как теги после поездки в такси («Чистота в салоне»): по каждому критерию из фиксированного списка пользователь либо ставит отметку, либо пропускает его. Критерии — это enum `FeedbackCriterion` (`AUDIENCE`, `CULTURE`, `ORGANIZATION`, `VENUE`, `PROGRAM`: «Аудитория», «Культурность», «Организация», «Площадка», «Программа»). Пользователь выбирает из списка (`FeedbackService.list_criteria()`) и не пишет названия сам. В БД хранится код в `feedback_scores.criterion` (`VARCHAR(20)` + CHECK), отметка — булево значение в `feedback_scores.positive`: `true` — хорошо, `false` — плохо. Пропущенный критерий — это отсутствие строки, а не `NULL`. Название и вопрос пользователю («Вход, начало вовремя и работа персонала — без проблем?») лежат в `CRITERION_QUESTIONS` в `app/models/enums.py`. Рейтинг мероприятия — доля положительных отметок от 0 до 1 по каждому критерию и общая: `count(*) FILTER (WHERE positive)` к `count(*)`. Цена enum: новый критерий — это правка кода и миграция (CHECK нужно обновить вручную).

---

## Структура проекта

```
you-can-book/
├── setup.ps1                   # подготовка и запуск одной командой
├── docker-compose.yml          # контейнер PostgreSQL (+ сервис api для запуска кода в Docker)
├── .env.example                # параметры контейнера (логин, пароль, порт)
└── api-service/                # Python-сервис (в ЛР2 здесь появится FastAPI)
    ├── requirements.txt
    ├── Dockerfile              # образ для запуска кода внутри Docker
    ├── .env.example            # строка подключения DATABASE_URL
    ├── alembic.ini             # настройки Alembic
    ├── alembic/
    │   ├── env.py              # подключение Alembic к БД и моделям
    │   └── versions/
    │       ├── 0001_initial_schema.py        # пользователи, каталог, брони
    │       ├── 0002_organizers_friends_feedback.py  # организаторы, друзья, отзывы
    │       ├── 0003_feedback_marks_boolean.py       # оценка 0..1 -> отметка «хорошо / плохо»
    │       └── 0004_feedback_criteria_enum.py       # справочник критериев -> enum
    ├── app/
    │   ├── config.py           # настройки из .env
    │   ├── db.py               # engine и фабрика сессий
    │   ├── security.py         # хеширование паролей (bcrypt)
    │   ├── models/             # ORM-модели: User, Location, Category, Event, Booking,
    │   │                       #   Friendship, EventInvitation, EventFeedback, FeedbackScore
    │   ├── repositories/       # CRUD-операции (слой доступа к данным)
    │   └── services/           # бизнес-логика сценариев и проверка прав (permissions.py)
    └── scripts/
        ├── seed.py             # заполнение тестовыми данными
        └── demo.py             # тестовый скрипт со всеми сценариями
```

Слои приложения:

```
 scripts/demo.py  (в ЛР2 — эндпоинты FastAPI)
        │  вызывает
        ▼
 services/        бизнес-правила: «нельзя забронировать отменённое мероприятие»,
        │         «изменять мероприятие может только его организатор»; делает commit
        ▼
 repositories/    CRUD и запросы: get, list, create, update, delete, фильтры каталога
        │         работает через сессию, делает только flush
        ▼
 models/          классы SQLAlchemy ↔ таблицы PostgreSQL
        │
        ▼
 PostgreSQL 16 (Docker)
```

---

## Что нужно установить

| Программа | Зачем | Проверка |
| --- | --- | --- |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | запуск PostgreSQL в контейнере | `docker --version`, `docker compose version` |
| [Python 3.11+](https://www.python.org/downloads/) (при установке отметить «Add python.exe to PATH») | запуск кода | `python --version` |

Перед работой Docker Desktop должен быть запущен (значок кита в трее).

Все команды ниже — для PowerShell в Windows.

---

## Шаг 1. Поднять PostgreSQL в Docker

Из корня проекта `you-can-book`:

```powershell
copy .env.example .env        # параметры контейнера; можно оставить как есть
docker compose up -d          # скачать образ postgres:16 и запустить контейнер в фоне
docker compose ps             # STATUS должен стать "Up ... (healthy)"
```

Что происходит:

- Docker скачивает образ `postgres:16` (только в первый раз).
- Создаётся контейнер `you-can-book-postgres`. При первом запуске PostgreSQL сам создаёт базу `you_can_book_db` и пользователя `you_can_book` с паролем `you_can_book` из переменных `POSTGRES_DB`, `POSTGRES_USER` и `POSTGRES_PASSWORD`.
- `ports: "5432:5432"` пробрасывает порт: программы на твоём компьютере подключаются к `localhost:5432` и попадают в контейнер.
- `volumes: postgres-data` хранит файлы БД в томе Docker. Данные переживают перезапуск и удаление контейнера.
- `networks: you-can-book-network` — сеть, в которой в ЛР5 окажутся все сервисы. Внутри неё они будут обращаться к БД по имени `postgres`.
- `healthcheck` каждые 5 секунд выполняет `pg_isready`. Статус `healthy` означает, что БД готова принимать подключения.

Если что-то пошло не так, посмотри логи: `docker compose logs postgres`.

### Проверить базу вручную (по желанию)

Через консоль `psql` внутри контейнера:

```powershell
docker exec -it you-can-book-postgres psql -U you_can_book -d you_can_book_db
```

```sql
\l          -- список баз
\dt         -- список таблиц (появятся после шага 3)
\d bookings -- структура таблицы: колонки, индексы, внешние ключи
SELECT * FROM events;
\q          -- выход
```

Или через вкладку **Database** в IDE от JetBrains (PyCharm Professional, DataGrip, IntelliJ IDEA Ultimate): `+` → Data Source → PostgreSQL:

| Поле | Значение |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| User | `you_can_book` |
| Password | `you_can_book` |
| Database | `you_can_book_db` |

---

## Шаг 2. Настроить Python-окружение

```powershell
cd api-service
python -m venv .venv                  # виртуальное окружение — свои пакеты для проекта
.venv\Scripts\Activate.ps1            # активировать; в начале строки появится (.venv)
pip install -r requirements.txt
copy .env.example .env                # строка подключения к БД
```

Если PowerShell пишет «выполнение сценариев отключено», один раз выполни
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` и повтори активацию.

Строка подключения в `api-service/.env`:

```
DATABASE_URL=postgresql+asyncpg://you_can_book:you_can_book@127.0.0.1:5432/you_can_book_db?ssl=disable
             └──── драйвер ─────┘ └─ логин ──┘ └─ пароль ─┘ └─ хост ─┘└порт┘└── база ───┘ └─ без SSL ─┘
```

`asyncpg` — асинхронный драйвер PostgreSQL. Он понадобится в ЛР2: FastAPI работает асинхронно.

**Все дальнейшие команды выполняются из папки `api-service` с активированным `.venv`.**

---

## Шаг 3. Создать таблицы миграцией Alembic

```powershell
alembic upgrade head      # применить все миграции -> создаются 11 таблиц
alembic current           # текущая версия схемы: 0004 (head)
```

Таблицы создаются не через `Base.metadata.create_all()`, а миграцией. Alembic хранит номер применённой версии в служебной таблице `alembic_version`, и любое будущее изменение схемы оформляется новой миграцией, а не ручным `ALTER TABLE`.

---

## Шаг 4. Заполнить тестовыми данными

```powershell
python -m scripts.seed
```

Скрипт сначала проверяет, что схема БД на последней миграции (иначе просит выполнить `alembic upgrade head`), затем очищает таблицы и создаёт данные:

| Что | Сколько |
| --- | --- |
| Пользователи | 6: `admin@ycb.ru` (ADMIN); `ivan@ycb.ru`, `olga@ycb.ru`, `pavel@ycb.ru` (CLIENT); `dmitry@ycb.ru` — концерты, театр, парк и `anna@ycb.ru` — лекторий (ORGANIZER); пароль у всех `password123` |
| Площадки | 4 |
| Категории | 6 |
| Мероприятия | 11: 9 будущих и 2 прошедших (для истории посещений и отзывов); у каждого есть организатор |
| Брони | 10 в статусах BOOKED, ATTENDED и CANCELLED |
| Друзья | Иван — Ольга, Ольга — Павел; заявка Павла Ивану ждёт ответа |
| Приглашения | Ольга зовёт Ивана на лекцию |
| Отзывы | 3 отзыва о прошедших мероприятиях |

Даты мероприятий считаются от текущего момента, поэтому будущие мероприятия всегда остаются будущими.

---

## Шаг 5. Запустить тестовый скрипт

```powershell
python -m scripts.demo          # результаты в консоль
python -m scripts.demo --sql    # плюс все SQL-запросы, которые генерирует SQLAlchemy
```

Скрипт сам перезагружает тестовые данные, поэтому его можно запускать повторно. Сценарии:

| № | Сценарий | Что показывает |
| --- | --- | --- |
| 0 | Подключение | версия PostgreSQL, количество строк в таблицах |
| 1 | Пользователи | регистрация, дубль email, вход с верным/неверным паролем, редактирование профиля |
| 2 | Каталог | фильтры по категории, датам, площадке; прошедшие мероприятия скрыты |
| 3 | Бронирование | бронь; повторная бронь (отклоняет сервис); прямой INSERT в обход сервиса (отклоняет индекс `ux_bookings_active`); бронь прошедшего мероприятия |
| 4 | Отмена брони | чужую бронь отменить нельзя; после отмены можно забронировать снова |
| 5 | Администратор и организатор | площадки и категории (только админ); мероприятие создаёт организатор, клиенту это запрещено; чужое мероприятие изменить нельзя; назначение роли |
| 6 | Перенос и отмена | организатор переносит своё мероприятие; список клиентов для уведомления; массовая отмена броней через `UPDATE ... RETURNING`; чужое мероприятие отменить нельзя |
| 7 | Брони и посещения | брони клиента, все активные брони; посещение отмечает только организатор этого мероприятия |
| 8 | Друзья | принять и отклонить заявку; заявка себе и повторная заявка; прямой INSERT встречной пары (индекс `ux_friendships_pair`); кто из друзей идёт; приглашение -> бронь в одной транзакции; ошибки приглашений |
| 9 | Отзывы | список критериев (enum) с вопросами; отзыв с частью отмеченных критериев; доля «хорошо» по критериям; повторный отзыв, отзыв без посещения, пустой отзыв, критерий не из списка, не булево значение; прямой INSERT второй отметки (составной PK) и кода вне enum (CHECK) |
| 10 | Удаление | `ON DELETE RESTRICT` (мероприятие с бронями, площадка с мероприятиями), `ON DELETE CASCADE` (брони, дружбы и отзывы пользователя), `ON DELETE SET NULL` (мероприятия удалённого организатора) |

---

## Вариант Б: запуск кода внутри Docker (если мешает VPN)

VPN, антивирус или другая программа на порту 5432 могут перехватывать подключения к `localhost`. Тогда Python-код можно запускать не на компьютере, а в контейнере, в одной Docker-сети с базой. В этом случае трафик вообще не выходит в сеть Windows:

```
 Вариант А (по умолчанию)                 Вариант Б
 Python на Windows                        контейнер api ──┐
   │ 127.0.0.1:5432                                       │ postgres:5432
   ▼  (VPN может перехватить)                             ▼ (сеть you-can-book-network)
 проброс порта Docker → postgres          контейнер postgres
```

Venv и `pip install` при этом не нужны: зависимости ставятся в образ. Из корня проекта:

```powershell
docker compose build api                               # один раз: собрать образ с зависимостями
docker compose run --rm api alembic upgrade head       # миграции
docker compose run --rm api python -m scripts.seed     # тестовые данные
docker compose run --rm api python -m scripts.demo     # демонстрация
docker compose run --rm api alembic current            # любая команда alembic
```

- `run --rm` создаёт временный контейнер, выполняет команду и удаляет контейнер.
- Папка `api-service` смонтирована в контейнер, поэтому изменения в коде видны без пересборки. Пересобирать (`docker compose build api`) нужно только после изменения `requirements.txt`.
- Строку подключения задаёт `docker-compose.yml`: хост `postgres` (имя сервиса), порт 5432. Файл `api-service/.env` в этом режиме не используется, потому что переменная окружения важнее.
- Миграции, созданные командой `docker compose run --rm api alembic revision --autogenerate -m "..."`, появятся в твоей папке `alembic/versions`.

---

## Дополнительное задание: работа с Alembic

### Основные команды

```powershell
alembic history           # список миграций: <base> -> 0001 -> 0002 -> 0003 -> 0004 (head)
alembic current           # какая версия применена к БД сейчас
alembic downgrade 0002    # откатить на шаг: отметки снова станут числами 0 и 1
alembic downgrade 0001    # откатить до удаления друзей, отзывов и организаторов
alembic downgrade base    # откатить все миграции -> все таблицы удалены
alembic upgrade head      # применить заново -> таблицы созданы
alembic upgrade head --sql  # не выполнять, а показать SQL миграций
alembic check             # проверить, совпадают ли модели и БД
```

### Демонстрация: добавить новое поле

1. В `app/models/user.py` добавь в класс `User` строку:
   ```python
   phone: Mapped[str | None] = mapped_column(String(20))
   ```
2. Сгенерируй миграцию. Alembic сравнит модели с БД и найдёт разницу:
   ```powershell
   alembic revision --autogenerate -m "add phone to users"
   ```
   В `alembic/versions/` появится файл с `op.add_column(...)` в `upgrade()` и `op.drop_column(...)` в `downgrade()`.
3. Примени и проверь:
   ```powershell
   alembic upgrade head
   alembic current           # <новый id> (head)
   docker exec -it you-can-book-postgres psql -U you_can_book -d you_can_book_db -c "\d users"
   ```
4. Откати:
   ```powershell
   alembic downgrade -1      # колонка phone удалена
   ```
5. Если поле не нужно, удали файл миграции и строку из модели.

### Что важно знать

- `--autogenerate` не всегда угадывает правильно. В начальной миграции он продублировал CHECK-ограничения для колонок-статусов, поэтому файл `0001_initial_schema.py` проверен и исправлен вручную. **Сгенерированную миграцию всегда нужно читать перед применением.**
- Alembic не сравнивает CHECK-ограничения. Когда в `UserRole` добавили `ORGANIZER`, autogenerate этого не заметил. Замена `ck_users_role` дописана в `0002` вручную. Её `downgrade()` сначала переводит организаторов в клиенты, иначе старое ограничение не создастся.
- Смена типа колонки `score` на `boolean` в `0003` тоже написана вручную: Alembic сам не знает, как перенести данные. Старые оценки переводятся правилом `score >= 0.5` -> `true`. Обратный перенос теряет точность: `true` станет `1.00`, `false` — `0.00`.
- Миграция `0004` заменяет справочник `feedback_criteria` на enum: названия переносятся в коды по таблице соответствия (`Аудитория` -> `AUDIENCE` и т. д.), CHECK по кодам и составной PK создаются вручную. Если в справочнике есть название, которого нет в enum, миграция остановится с ошибкой и ничего не потеряет. Обратная миграция воссоздаёт справочник с пятью критериями.
- Все ограничения называются по единому правилу (`naming_convention` в `app/models/base.py`): `pk_users`, `fk_bookings_event_id_events`, `ck_bookings_status`. Без имён Alembic не сможет удалить или изменить ограничение в следующих миграциях.

---

## Остановка и сброс

```powershell
docker compose stop       # остановить контейнер (данные сохраняются)
docker compose start      # запустить снова
docker compose down       # удалить контейнер (данные в томе сохраняются)
docker compose down -v    # удалить контейнер И том с данными — полный сброс БД
```

---

## Частые проблемы

| Проблема | Причина и решение |
| --- | --- |
| `port is already allocated` или `password authentication failed` при верном пароле | На компьютере уже установлен PostgreSQL, и он занимает порт 5432. Поставь `POSTGRES_PORT=5433` в корневом `.env`, а в `api-service/.env` замени `127.0.0.1:5432` на `127.0.0.1:5433`. Затем `docker compose up -d` |
| Поменял логин/пароль в `.env`, а подключиться не получается | Переменные `POSTGRES_*` применяются только при **первом** создании базы. Старая база осталась в томе: `docker compose down -v`, затем `docker compose up -d` |
| `error during connect` / `cannot find the file specified` | Docker Desktop не запущен |
| `ModuleNotFoundError: No module named 'app'` | Команда запущена не из папки `api-service` |
| `ConnectionDoesNotExistError: connection was closed in the middle of operation` / `WinError 64` | Соединение сброшено при подключении. 1) База ещё инициализируется после первого `docker compose up` — подожди статуса `healthy` в `docker compose ps`. 2) В `.env` хост `localhost` — замени на `127.0.0.1` и добавь `?ssl=disable` (уже так в `.env.example`). 3) Порт 5432 занят другой программой — проверь `netstat -ano \| findstr :5432` |
| Не помогает ни смена порта, ни `127.0.0.1` (включён VPN) | Запускай код внутри Docker: раздел «Вариант Б» |
| Поменял `POSTGRES_PORT`, а `docker compose up -d` пишет `Running` и порт старый | Compose не увидел изменение: проверь, что правка в **корневом** `.env`, затем `docker compose up -d --force-recreate`. Проверка: `docker compose port postgres 5432` |
| `relation "..." does not exist` или «Схема БД на версии ..., а нужна 0004» | Миграции не применены или применены не все: `alembic upgrade head`, затем `python -m scripts.seed` |
| Предупреждение `the attribute version is obsolete` | Поле `version` в Docker Compose v2 устарело, в нашем `docker-compose.yml` его нет |
