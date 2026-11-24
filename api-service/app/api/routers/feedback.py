from fastapi import APIRouter, status

from app.api.deps import CurrentUser, Feedback
from app.schemas.feedback import CriterionOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/criteria", response_model=list[CriterionOut])
async def list_criteria(feedback: Feedback):
    # Фиксированный список критериев с вопросами для формы отзыва
    return [CriterionOut(code=c, title=t, question=q) for c, t, q in feedback.list_criteria()]


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(feedback_id: int, user: CurrentUser, feedback: Feedback):
    await feedback.delete_feedback(feedback_id, user)
