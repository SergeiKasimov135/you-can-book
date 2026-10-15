from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.enums import FeedbackCriterion, varchar_enum

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.user import User


class EventFeedback(CreatedAtMixin, Base):
    # Отзыв посетителя о мероприятии

    __tablename__ = "event_feedback"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_feedback_event_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    comment: Mapped[str | None] = mapped_column(Text)

    event: Mapped["Event"] = relationship()
    user: Mapped["User"] = relationship()
    # Отметки удаляются вместе с отзывом (CASCADE)
    scores: Mapped[list["FeedbackScore"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan", passive_deletes=True
    )


class FeedbackScore(Base):
    # Отметка по одному критерию в отзыве: True — «хорошо», False — «плохо»

    __tablename__ = "feedback_scores"

    feedback_id: Mapped[int] = mapped_column(
        ForeignKey("event_feedback.id", ondelete="CASCADE"), primary_key=True
    )
    criterion: Mapped[FeedbackCriterion] = mapped_column(
        varchar_enum(FeedbackCriterion, "criterion"), primary_key=True
    )
    positive: Mapped[bool]  # True — хорошо, False — плохо

    feedback: Mapped["EventFeedback"] = relationship(back_populates="scores")
