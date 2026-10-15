from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import CRITERION_QUESTIONS, EventFeedback, FeedbackCriterion, FeedbackScore
from app.repositories.base import BaseRepository


def share(positive: int, total: int) -> Decimal | None:
    # Доля положительных отметок от 0 до 1 (None, если отметок нет)
    if total == 0:
        return None
    return (Decimal(positive) / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class CriterionStat:
    criterion: FeedbackCriterion
    positive: int  # сколько человек отметили «хорошо»
    total: int  # сколько человек вообще отметили этот критерий

    @property
    def title(self) -> str:
        return CRITERION_QUESTIONS[self.criterion][0]

    @property
    def share(self) -> Decimal | None:
        return share(self.positive, self.total)


class FeedbackRepository(BaseRepository[EventFeedback]):
    model = EventFeedback

    async def get_by_event_user(self, event_id: int, user_id: int) -> EventFeedback | None:
        stmt = select(EventFeedback).where(
            EventFeedback.event_id == event_id, EventFeedback.user_id == user_id
        )
        return await self.session.scalar(stmt)

    async def get_with_details(self, feedback_id: int) -> EventFeedback | None:
        stmt = (
            select(EventFeedback)
            .where(EventFeedback.id == feedback_id)
            .options(
                selectinload(EventFeedback.scores),
                selectinload(EventFeedback.user),
                selectinload(EventFeedback.event),
            )
        )
        return await self.session.scalar(stmt)

    async def list_for_event(self, event_id: int) -> Sequence[EventFeedback]:
        stmt = (
            select(EventFeedback)
            .where(EventFeedback.event_id == event_id)
            .options(
                selectinload(EventFeedback.scores),
                selectinload(EventFeedback.user),
            )
            .order_by(EventFeedback.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def stats_for_event(self, event_id: int) -> list[CriterionStat]:
        # Для каждого критерия: сколько отметок «хорошо» и сколько всего (GROUP BY)
        stmt = (
            select(
                FeedbackScore.criterion,
                func.count().filter(FeedbackScore.positive).label("positive"),
                func.count().label("total"),
            )
            .join(EventFeedback, EventFeedback.id == FeedbackScore.feedback_id)
            .where(EventFeedback.event_id == event_id)
            .group_by(FeedbackScore.criterion)
            .order_by(FeedbackScore.criterion)
        )
        return [CriterionStat(r.criterion, r.positive, r.total) for r in await self.session.execute(stmt)]

    async def totals_for_event(self, event_id: int) -> tuple[int, int, int]:
        # Число отзывов, всего отметок и отметок «хорошо» по мероприятию
        stmt = (
            select(
                func.count(func.distinct(EventFeedback.id)),
                func.count(FeedbackScore.feedback_id),
                func.count(FeedbackScore.feedback_id).filter(FeedbackScore.positive),
            )
            .select_from(EventFeedback)
            .outerjoin(FeedbackScore, FeedbackScore.feedback_id == EventFeedback.id)
            .where(EventFeedback.event_id == event_id)
        )
        feedback_count, total, positive = (await self.session.execute(stmt)).one()
        return feedback_count, total, positive
