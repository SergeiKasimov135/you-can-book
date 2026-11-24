"""feedback_scores: оценка 0..1 -> отметка «хорошо / плохо» (boolean)"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_feedback_scores_score_range"), "feedback_scores", type_="check")
    op.alter_column(
        "feedback_scores",
        "score",
        existing_type=sa.Numeric(precision=3, scale=2),
        type_=sa.Boolean(),
        existing_nullable=False,
        postgresql_using="score >= 0.5",
    )
    op.alter_column("feedback_scores", "score", new_column_name="positive")


def downgrade() -> None:
    # True -> 1.00, False -> 0.00 (исходная точность оценок восстановить нельзя)
    op.alter_column("feedback_scores", "positive", new_column_name="score")
    op.alter_column(
        "feedback_scores",
        "score",
        existing_type=sa.Boolean(),
        type_=sa.Numeric(precision=3, scale=2),
        existing_nullable=False,
        postgresql_using="CASE WHEN score THEN 1 ELSE 0 END",
    )
    op.create_check_constraint(
        op.f("ck_feedback_scores_score_range"), "feedback_scores", "score >= 0 AND score <= 1"
    )
