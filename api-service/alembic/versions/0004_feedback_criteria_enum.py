"""Критерии отзыва: справочник feedback_criteria -> enum"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (название в справочнике, код enum, вопрос)
CRITERIA = [
    ("Аудитория", "AUDIENCE", "Публика и атмосфера в зале были приятными?"),
    ("Культурность", "CULTURE", "Мероприятие было содержательным и культурным?"),
    ("Организация", "ORGANIZATION", "Вход, начало вовремя и работа персонала — без проблем?"),
    ("Площадка", "VENUE", "На площадке удобно: звук, видимость, чистота?"),
    ("Программа", "PROGRAM", "Программа соответствовала анонсу?"),
]
CODES = ", ".join(f"'{code}'" for _, code, _ in CRITERIA)


def upgrade() -> None:
    op.add_column("feedback_scores", sa.Column("criterion", sa.String(length=20), nullable=True))

    mapping = " ".join(f"WHEN '{name}' THEN '{code}'" for name, code, _ in CRITERIA)
    op.execute(
        f"UPDATE feedback_scores s SET criterion = CASE c.name {mapping} END "
        "FROM feedback_criteria c WHERE c.id = s.criterion_id"
    )
    unmapped = op.get_bind().scalar(sa.text("SELECT count(*) FROM feedback_scores WHERE criterion IS NULL"))
    if unmapped:
        raise RuntimeError(
            f"{unmapped} отметок относятся к критериям, которых нет в enum FeedbackCriterion: "
            "сначала перенесите или удалите их вручную"
        )

    op.alter_column("feedback_scores", "criterion", existing_type=sa.String(length=20), nullable=False)
    op.drop_constraint(op.f("pk_feedback_scores"), "feedback_scores", type_="primary")
    op.drop_constraint(
        op.f("fk_feedback_scores_criterion_id_feedback_criteria"), "feedback_scores", type_="foreignkey"
    )
    op.drop_index(op.f("ix_feedback_scores_criterion_id"), table_name="feedback_scores")
    op.drop_column("feedback_scores", "criterion_id")
    op.create_primary_key(op.f("pk_feedback_scores"), "feedback_scores", ["feedback_id", "criterion"])
    op.create_check_constraint(
        op.f("ck_feedback_scores_criterion"), "feedback_scores", f"criterion IN ({CODES})"
    )
    op.drop_table("feedback_criteria")


def downgrade() -> None:
    op.create_table(
        "feedback_criteria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_criteria")),
        sa.UniqueConstraint("name", name=op.f("uq_feedback_criteria_name")),
    )
    criteria = sa.table(
        "feedback_criteria", sa.column("name", sa.String), sa.column("description", sa.String)
    )
    op.bulk_insert(criteria, [{"name": name, "description": text} for name, _, text in CRITERIA])

    op.add_column("feedback_scores", sa.Column("criterion_id", sa.Integer(), nullable=True))
    mapping = " ".join(f"WHEN '{code}' THEN '{name}'" for name, code, _ in CRITERIA)
    op.execute(
        "UPDATE feedback_scores s SET criterion_id = c.id FROM feedback_criteria c "
        f"WHERE c.name = CASE s.criterion {mapping} END"
    )
    op.alter_column("feedback_scores", "criterion_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint(op.f("ck_feedback_scores_criterion"), "feedback_scores", type_="check")
    op.drop_constraint(op.f("pk_feedback_scores"), "feedback_scores", type_="primary")
    op.drop_column("feedback_scores", "criterion")
    op.create_primary_key(op.f("pk_feedback_scores"), "feedback_scores", ["feedback_id", "criterion_id"])
    op.create_foreign_key(
        op.f("fk_feedback_scores_criterion_id_feedback_criteria"),
        "feedback_scores",
        "feedback_criteria",
        ["criterion_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_feedback_scores_criterion_id"), "feedback_scores", ["criterion_id"])
