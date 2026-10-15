"""organizers, friends, invitations, feedback"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- Роль ORGANIZER и организатор мероприятия
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_role"), "users", "role IN ('CLIENT', 'ORGANIZER', 'ADMIN')"
    )

    op.add_column("events", sa.Column("organizer_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_events_organizer_id"), "events", ["organizer_id"])
    op.create_foreign_key(
        op.f("fk_events_organizer_id_users"),
        "events",
        "users",
        ["organizer_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---------- Друзья
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("addressee_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("status IN ('PENDING', 'ACCEPTED')", name=op.f("ck_friendships_status")),
        sa.CheckConstraint("requester_id <> addressee_id", name=op.f("ck_friendships_not_self")),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_friendships_requester_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["addressee_id"],
            ["users.id"],
            name=op.f("fk_friendships_addressee_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_friendships")),
    )
    op.create_index(op.f("ix_friendships_requester_id"), "friendships", ["requester_id"])
    op.create_index(op.f("ix_friendships_addressee_id"), "friendships", ["addressee_id"])
    # Одна дружба на пару в любом направлении
    op.create_index(
        "ux_friendships_pair",
        "friendships",
        [
            sa.literal_column("least(requester_id, addressee_id)"),
            sa.literal_column("greatest(requester_id, addressee_id)"),
        ],
        unique=True,
    )

    # ---------- Приглашения друзей на мероприятия
    op.create_table(
        "event_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("inviter_id", sa.Integer(), nullable=False),
        sa.Column("invitee_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'DECLINED')", name=op.f("ck_event_invitations_status")
        ),
        sa.CheckConstraint("inviter_id <> invitee_id", name=op.f("ck_event_invitations_not_self")),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_invitations_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inviter_id"],
            ["users.id"],
            name=op.f("fk_event_invitations_inviter_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invitee_id"],
            ["users.id"],
            name=op.f("fk_event_invitations_invitee_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_invitations")),
        sa.UniqueConstraint(
            "event_id", "inviter_id", "invitee_id", name="uq_event_invitations_triple"
        ),
    )
    op.create_index(op.f("ix_event_invitations_event_id"), "event_invitations", ["event_id"])
    op.create_index(op.f("ix_event_invitations_inviter_id"), "event_invitations", ["inviter_id"])
    op.create_index(op.f("ix_event_invitations_invitee_id"), "event_invitations", ["invitee_id"])

    # ---------- Отзывы
    op.create_table(
        "feedback_criteria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_criteria")),
        sa.UniqueConstraint("name", name=op.f("uq_feedback_criteria_name")),
    )

    op.create_table(
        "event_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_feedback_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_event_feedback_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_feedback")),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_feedback_event_user"),
    )
    op.create_index(op.f("ix_event_feedback_event_id"), "event_feedback", ["event_id"])
    op.create_index(op.f("ix_event_feedback_user_id"), "event_feedback", ["user_id"])

    op.create_table(
        "feedback_scores",
        sa.Column("feedback_id", sa.Integer(), nullable=False),
        sa.Column("criterion_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 1", name=op.f("ck_feedback_scores_score_range")),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["event_feedback.id"],
            name=op.f("fk_feedback_scores_feedback_id_event_feedback"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["criterion_id"],
            ["feedback_criteria.id"],
            name=op.f("fk_feedback_scores_criterion_id_feedback_criteria"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("feedback_id", "criterion_id", name=op.f("pk_feedback_scores")),
    )
    op.create_index(op.f("ix_feedback_scores_criterion_id"), "feedback_scores", ["criterion_id"])


def downgrade() -> None:
    # Сначала таблицы, которые ссылаются на другие
    op.drop_table("feedback_scores")
    op.drop_table("event_feedback")
    op.drop_table("feedback_criteria")
    op.drop_table("event_invitations")
    op.drop_table("friendships")

    op.drop_constraint(op.f("fk_events_organizer_id_users"), "events", type_="foreignkey")
    op.drop_index(op.f("ix_events_organizer_id"), table_name="events")
    op.drop_column("events", "organizer_id")

    # В старой схеме роли ORGANIZER нет: такие пользователи становятся клиентами
    op.execute("UPDATE users SET role = 'CLIENT' WHERE role = 'ORGANIZER'")
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_role"), "users", "role IN ('CLIENT', 'ADMIN')")
