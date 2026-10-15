"""initial schema: users, locations, categories, events, event_categories, bookings

Revision ID: 0001
Revises:
Create Date: 2026-10-15 15:47:33

Сгенерирована командой `alembic revision --autogenerate` и проверена вручную:
autogenerate дублировал CHECK-ограничения для enum-колонок, дубли удалены,
статусы и роли описаны как VARCHAR(20) + именованный CHECK.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_categories_name")),
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.CheckConstraint("capacity > 0", name=op.f("ck_locations_capacity_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), server_default="CLIENT", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("role IN ('CLIENT', 'ADMIN')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="SCHEDULED", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("status IN ('SCHEDULED', 'CANCELLED')", name=op.f("ck_events_status")),
        sa.CheckConstraint("price >= 0", name=op.f("ck_events_price_non_negative")),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name=op.f("fk_events_location_id_locations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index(op.f("ix_events_event_date"), "events", ["event_date"])
    op.create_index(op.f("ix_events_location_id"), "events", ["location_id"])

    op.create_table(
        "event_categories",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_categories_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_event_categories_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "category_id", name=op.f("pk_event_categories")),
    )

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="BOOKED", nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('BOOKED', 'CANCELLED', 'ATTENDED')", name=op.f("ck_bookings_status")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_bookings_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_bookings_event_id_events"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(op.f("ix_bookings_user_id"), "bookings", ["user_id"])
    op.create_index(op.f("ix_bookings_event_id"), "bookings", ["event_id"])
    # Не больше одной активной брони клиента на одно мероприятие
    op.create_index(
        "ux_bookings_active",
        "bookings",
        ["user_id", "event_id"],
        unique=True,
        postgresql_where=sa.text("status = 'BOOKED'"),
    )


def downgrade() -> None:
    # Удаляем в обратном порядке: сначала таблицы, которые ссылаются на другие
    op.drop_table("bookings")
    op.drop_table("event_categories")
    op.drop_table("events")
    op.drop_table("users")
    op.drop_table("locations")
    op.drop_table("categories")
