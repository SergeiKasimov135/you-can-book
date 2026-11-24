from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CRITERION_QUESTIONS,
    BookingStatus,
    EventFeedback,
    FeedbackCriterion,
    FeedbackScore,
    User,
)
from app.repositories import (
    BookingRepository,
    CriterionStat,
    EventRepository,
    FeedbackRepository,
    share,
)
from app.services.exceptions import AlreadyExistsError, BusinessRuleError, NotFoundError
from app.services.permissions import require_admin


@dataclass
class EventRating:
    # Сводка отметок мероприятия

    event_id: int
    feedback_count: int
    positive: int  # отметок «хорошо» по всем критериям
    total: int  # всего отметок
    overall: Decimal | None  # общая доля положительных
    by_criterion: list[CriterionStat]


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.feedback = FeedbackRepository(session)
        self.events = EventRepository(session)
        self.bookings = BookingRepository(session)

    # ---------- Критерии ----------
    @staticmethod
    def list_criteria() -> list[tuple[FeedbackCriterion, str, str]]:
        # Список для выбора в интерфейсе: (код, название, вопрос)
        return [(code, title, question) for code, (title, question) in CRITERION_QUESTIONS.items()]

    # ---------- Отзывы ----------
    async def leave_feedback(
        self,
        actor: User,
        event_id: int,
        marks: Mapping[FeedbackCriterion, bool],
        comment: str | None = None,
    ) -> EventFeedback:
        if await self.events.get(event_id) is None:
            raise NotFoundError(f"Мероприятие {event_id} не найдено")
        attended = await self.bookings.list_filtered(
            user_id=actor.id, event_id=event_id, status=BookingStatus.ATTENDED
        )
        if not attended:
            raise BusinessRuleError("Отзыв может оставить только посетитель мероприятия")
        if not marks:
            raise BusinessRuleError("Нужно отметить хотя бы один критерий")
        if await self.feedback.get_by_event_user(event_id, actor.id):
            raise AlreadyExistsError("Вы уже оставили отзыв об этом мероприятии")

        for criterion, mark in marks.items():
            if not isinstance(criterion, FeedbackCriterion):  # критерий выбирают только из enum
                raise BusinessRuleError(f"Неизвестный критерий: {criterion!r}")
            if not isinstance(mark, bool):  # 1, 0.9, "yes" — не булевы значения
                raise BusinessRuleError(f"Отметка по критерию {criterion.value} должна быть True или False")

        feedback = await self.feedback.create(
            event_id=event_id,
            user_id=actor.id,
            comment=comment,
            scores=[FeedbackScore(criterion=criterion, positive=mark) for criterion, mark in marks.items()],
        )
        await self.session.commit()
        return await self.feedback.get_with_details(feedback.id)

    async def list_for_event(self, event_id: int) -> Sequence[EventFeedback]:
        return await self.feedback.list_for_event(event_id)

    async def rating(self, event_id: int) -> EventRating:
        feedback_count, total, positive = await self.feedback.totals_for_event(event_id)
        return EventRating(
            event_id=event_id,
            feedback_count=feedback_count,
            positive=positive,
            total=total,
            overall=share(positive, total),
            by_criterion=await self.feedback.stats_for_event(event_id),
        )

    async def delete_feedback(self, feedback_id: int, actor: User) -> None:
        # Удалить отзыв может автор или администратор
        feedback = await self.feedback.get(feedback_id)
        if feedback is None:
            raise NotFoundError(f"Отзыв {feedback_id} не найден")
        if feedback.user_id != actor.id:
            require_admin(actor)
        await self.feedback.delete(feedback)
        await self.session.commit()
