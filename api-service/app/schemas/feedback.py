from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, StrictBool

from app.models import FeedbackCriterion
from app.schemas.common import ORMModel
from app.schemas.users import UserShort


class CriterionOut(BaseModel):
    code: FeedbackCriterion
    title: str
    question: str


class FeedbackCreate(BaseModel):
    # Ключи — только коды из enum, значения — строго true/false
    marks: dict[FeedbackCriterion, StrictBool] = Field(min_length=1)
    comment: str | None = None


class ScoreOut(ORMModel):
    criterion: FeedbackCriterion
    positive: bool


class FeedbackOut(ORMModel):
    id: int
    event_id: int
    comment: str | None
    created_at: datetime
    user: UserShort
    scores: list[ScoreOut]


class CriterionStatOut(ORMModel):
    criterion: FeedbackCriterion
    title: str
    positive: int
    total: int
    share: Decimal | None


class RatingOut(ORMModel):
    event_id: int
    feedback_count: int
    positive: int
    total: int
    overall: Decimal | None
    by_criterion: list[CriterionStatOut]
