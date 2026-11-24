from fastapi import APIRouter, status

from app.api.deps import Bookings, CurrentUser, Friends
from app.models import InvitationStatus
from app.schemas.bookings import BookingOut, InvitationAnswerOut, InvitationCreate, InvitationOut

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def invite(data: InvitationCreate, user: CurrentUser, friends: Friends):
    return await friends.invite(user, data.friend_id, data.event_id, data.message)


@router.get("", response_model=list[InvitationOut])
async def my_invitations(user: CurrentUser, friends: Friends, status: InvitationStatus | None = None):
    return await friends.list_invitations(user.id, status)


async def _answer(invitation_id: int, accept: bool, user, friends, bookings) -> InvitationAnswerOut:
    invitation, booking = await friends.respond(invitation_id, user, accept)
    # Бронь перечитывается с мероприятием и пользователем для ответа
    booking_out = BookingOut.model_validate(await bookings.get(booking.id)) if booking else None
    return InvitationAnswerOut(invitation=InvitationOut.model_validate(invitation), booking=booking_out)


@router.post("/{invitation_id}/accept", response_model=InvitationAnswerOut)
async def accept(invitation_id: int, user: CurrentUser, friends: Friends, bookings: Bookings):
    # Принятие приглашения создаёт бронь в той же транзакции
    return await _answer(invitation_id, True, user, friends, bookings)


@router.post("/{invitation_id}/decline", response_model=InvitationAnswerOut)
async def decline(invitation_id: int, user: CurrentUser, friends: Friends, bookings: Bookings):
    return await _answer(invitation_id, False, user, friends, bookings)
