from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import Bookings, Catalog, CurrentUser, Feedback, Friends, OrganizerUser
from app.schemas.bookings import BookingOut
from app.schemas.catalog import EventChangeOut, EventCreate, EventOut, EventUpdate
from app.schemas.feedback import FeedbackCreate, FeedbackOut, RatingOut
from app.schemas.users import UserShort
from app.services import EventChange

router = APIRouter(prefix="/events", tags=["events"])


def _change_out(result: EventChange) -> EventChangeOut:
    return EventChangeOut(
        event=EventOut.model_validate(result.event),
        changes=sorted(result.changes),
        notify_user_ids=result.recipients,
    )


@router.get("", response_model=list[EventOut])
async def list_events(
    catalog: Catalog,
    category_id: int | None = None,
    location_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_past: bool = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    # Каталог: по умолчанию только будущие и не отменённые мероприятия
    return await catalog.list_catalog(
        include_past=include_past,
        category_id=category_id,
        location_id=location_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )


@router.get("/my", response_model=list[EventOut])
async def my_events(organizer: OrganizerUser, catalog: Catalog):
    # Объявлен до /{event_id}, иначе "my" попытались бы разобрать как id
    return await catalog.list_my_events(organizer)


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: int, catalog: Catalog):
    return await catalog.get_event(event_id)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(data: EventCreate, organizer: OrganizerUser, catalog: Catalog):
    return await catalog.create_event(organizer, **data.model_dump())


@router.patch("/{event_id}", response_model=EventChangeOut)
async def update_event(event_id: int, data: EventUpdate, user: OrganizerUser, catalog: Catalog):
    fields = data.model_dump(exclude_unset=True)
    category_ids = fields.pop("category_ids", None)
    return _change_out(await catalog.update_event(event_id, user, category_ids=category_ids, **fields))


@router.post("/{event_id}/cancel", response_model=EventChangeOut)
async def cancel_event(event_id: int, user: OrganizerUser, catalog: Catalog):
    return _change_out(await catalog.cancel_event(event_id, user))


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: int, user: OrganizerUser, catalog: Catalog):
    await catalog.delete_event(event_id, user)


@router.get("/{event_id}/bookings", response_model=list[BookingOut])
async def event_bookings(event_id: int, user: OrganizerUser, bookings: Bookings):
    # Список гостей — организатору мероприятия или администратору
    return await bookings.list_for_event(event_id, user)


@router.get("/{event_id}/friends", response_model=list[UserShort])
async def friends_going(event_id: int, user: CurrentUser, friends: Friends):
    # Кто из моих друзей уже записался
    return await friends.friends_going(user.id, event_id)


@router.get("/{event_id}/feedback", response_model=list[FeedbackOut])
async def event_feedback(event_id: int, feedback: Feedback):
    return await feedback.list_for_event(event_id)


@router.post("/{event_id}/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def leave_feedback(event_id: int, data: FeedbackCreate, user: CurrentUser, feedback: Feedback):
    return await feedback.leave_feedback(user, event_id, data.marks, data.comment)


@router.get("/{event_id}/rating", response_model=RatingOut)
async def event_rating(event_id: int, catalog: Catalog, feedback: Feedback):
    await catalog.get_event(event_id)  # 404, если мероприятия нет
    return await feedback.rating(event_id)
