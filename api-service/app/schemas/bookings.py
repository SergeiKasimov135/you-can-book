from datetime import datetime

from pydantic import BaseModel, Field

from app.models import BookingStatus, FriendshipStatus, InvitationStatus
from app.schemas.common import ORMModel
from app.schemas.users import UserShort


class BookingCreate(BaseModel):
    event_id: int
    comment: str | None = Field(default=None, max_length=255)


class BookingEvent(ORMModel):
    id: int
    title: str
    event_date: datetime


class BookingOut(ORMModel):
    id: int
    status: BookingStatus
    comment: str | None
    created_at: datetime
    event: BookingEvent
    user: UserShort


# ---------- Друзья ----------
class FriendRequestCreate(BaseModel):
    user_id: int


class FriendRequestOut(ORMModel):
    id: int
    requester_id: int
    addressee_id: int
    status: FriendshipStatus
    created_at: datetime


# ---------- Приглашения ----------
class InvitationCreate(BaseModel):
    friend_id: int
    event_id: int
    message: str | None = Field(default=None, max_length=255)


class InvitationOut(ORMModel):
    id: int
    status: InvitationStatus
    message: str | None
    created_at: datetime
    event: BookingEvent
    inviter: UserShort
    invitee: UserShort


class InvitationAnswerOut(BaseModel):
    invitation: InvitationOut
    booking: BookingOut | None
