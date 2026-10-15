# You Can Book

Распределённое приложение агентства досуга: каталог городских мероприятий и бронирование мест (оплата на месте).

Текущее состояние: **ЛР1** — база данных PostgreSQL в Docker, модели SQLAlchemy, CRUD, миграции Alembic, тестовые данные и демонстрационный скрипт.

---

## Структура проекта

```
you-can-book/
├── docker-compose.yml          # контейнер PostgreSQL
├── .env.example                # параметры контейнера (логин, пароль, порт)
└── api-service/                # Python-сервис (в ЛР2 здесь появится FastAPI)
    ├── requirements.txt
    ├── .env.example            # строка подключения DATABASE_URL
    ├── alembic.ini             # настройки Alembic
    ├── alembic/
    │   ├── env.py              # подключение Alembic к БД и моделям
    │   └── versions/
    │       └── 0001_initial_schema.py
    ├── app/
    │   ├── config.py           # настройки из .env
    │   ├── db.py               # engine и фабрика сессий
    │   ├── security.py         # хеширование паролей (bcrypt)
    │   ├── models/             # ORM-модели: User, Location, Category, Event, Booking
    │   ├── repositories/       # CRUD-операции (слой доступа к данным)
    │   └── services/           # бизнес-логика сценариев
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
        │         «отменить бронь может только владелец или админ»; делает commit
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
DATABASE_URL=postgresql+asyncpg://you_can_book:you_can_book@localhost:5432/you_can_book_db
             └──── драйвер ─────┘ └─ логин ──┘ └─ пароль ─┘ └─ хост ─┘└порт┘└── база ───┘
```

`asyncpg` — асинхронный драйвер PostgreSQL. Он понадобится в ЛР2: FastAPI работает асинхронно.

**Все дальнейшие команды выполняются из папки `api-service` с активированным `.venv`.**

---

## Шаг 3. Создать таблицы миграцией Alembic

```powershell
alembic upgrade head      # применить все миграции -> создаются 6 таблиц
alembic current           # текущая версия схемы: 0001 (head)
```

Таблицы создаются не через `Base.metadata.create_all()`, а миграцией. Alembic хранит номер применённой версии в служебной таблице `alembic_version`, и любое будущее изменение схемы оформляется новой миграцией, а не ручным `ALTER TABLE`.

---

## Шаг 4. Заполнить тестовыми данными

```powershell
python -m scripts.seed
```

Скрипт очищает таблицы и создаёт данные:

| Что | Сколько |
| --- | --- |
| Пользователи | 4: `admin@ycb.ru` (ADMIN), `ivan@ycb.ru`, `olga@ycb.ru`, `pavel@ycb.ru` (CLIENT); пароль у всех `password123` |
| Площадки | 4 |
| Категории | 6 |
| Мероприятия | 11: 9 будущих и 2 прошедших (для истории посещений) |
| Брони | 8 в статусах BOOKED, ATTENDED и CANCELLED |

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
| 5 | Рекомендации | статистика интересов по категориям и список кандидатов (вход для gRPC в ЛР3) |
| 6 | CRUD администратора | площадки, категории, мероприятия; связь M:N `event_categories`; мероприятие без категорий отклоняется |
| 7 | Перенос и отмена | список клиентов для уведомления; массовая отмена броней через `UPDATE ... RETURNING` |
| 8 | Брони для админа | брони любого клиента, все активные брони, отметка посещения |
| 9 | Удаление | `ON DELETE RESTRICT` (мероприятие с бронями, площадка с мероприятиями) и `ON DELETE CASCADE` (связи категорий, брони пользователя) |

---

## Дополнительное задание: работа с Alembic

### Основные команды

```powershell
alembic history           # список миграций: <base> -> 0001 (head)
alembic current           # какая версия применена к БД сейчас
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
| `port is already allocated` или `password authentication failed` при верном пароле | На компьютере уже установлен PostgreSQL, и он занимает порт 5432. Поставь `POSTGRES_PORT=5433` в корневом `.env`, а в `api-service/.env` замени `localhost:5432` на `localhost:5433`. Затем `docker compose up -d` |
| Поменял логин/пароль в `.env`, а подключиться не получается | Переменные `POSTGRES_*` применяются только при **первом** создании базы. Старая база осталась в томе: `docker compose down -v`, затем `docker compose up -d` |
| `error during connect` / `cannot find the file specified` | Docker Desktop не запущен |
| `ModuleNotFoundError: No module named 'app'` | Команда запущена не из папки `api-service` |
| `relation "users" does not exist` | Таблицы не созданы: `alembic upgrade head` |
| Предупреждение `the attribute version is obsolete` | Поле `version` в Docker Compose v2 устарело, в нашем `docker-compose.yml` его нет |
