from collections.abc import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.models import (
    Booking,
    BookingStatus,
    EventInvitation,
    Friendship,
    FriendshipStatus,
    InvitationStatus,
    User,
)
from app.repositories.base import BaseRepository


def _pair(a: int, b: int):
    # Дружба между a и b в любом направлении
    return or_(
        and_(Friendship.requester_id == a, Friendship.addressee_id == b),
        and_(Friendship.requester_id == b, Friendship.addressee_id == a),
    )


class FriendshipRepository(BaseRepository[Friendship]):
    model = Friendship

    async def get_between(self, a: int, b: int) -> Friendship | None:
        return await self.session.scalar(select(Friendship).where(_pair(a, b)))

    async def are_friends(self, a: int, b: int) -> bool:
        friendship = await self.get_between(a, b)
        return friendship is not None and friendship.status == FriendshipStatus.ACCEPTED

    async def list_friends(self, user_id: int) -> Sequence[User]:
        # Другая сторона каждой принятой дружбы
        accepted = select(Friendship).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        ).subquery()
        friend_id = select(accepted.c.requester_id).where(accepted.c.addressee_id == user_id).union(
            select(accepted.c.addressee_id).where(accepted.c.requester_id == user_id)
        )
        stmt = select(User).where(User.id.in_(friend_id)).order_by(User.full_name)
        return (await self.session.scalars(stmt)).all()

    async def list_incoming(self, user_id: int) -> Sequence[Friendship]:
        # Входящие заявки, ожидающие ответа
        stmt = (
            select(Friendship)
            .where(Friendship.addressee_id == user_id, Friendship.status == FriendshipStatus.PENDING)
            .options(selectinload(Friendship.requester))
            .order_by(Friendship.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def friends_going(self, user_id: int, event_id: int) -> Sequence[User]:
        # Кто из друзей уже забронировал мероприятие
        friends = [f.id for f in await self.list_friends(user_id)]
        stmt = (
            select(User)
            .join(Booking, Booking.user_id == User.id)
            .where(
                User.id.in_(friends),
                Booking.event_id == event_id,
                Booking.status == BookingStatus.BOOKED,
            )
            .order_by(User.full_name)
        )
        return (await self.session.scalars(stmt)).all()


_INVITATION_DETAILS = (
    selectinload(EventInvitation.event),
    selectinload(EventInvitation.inviter),
    selectinload(EventInvitation.invitee),
)


class InvitationRepository(BaseRepository[EventInvitation]):
    model = EventInvitation

    async def get_with_details(self, invitation_id: int) -> EventInvitation | None:
        stmt = (
            select(EventInvitation)
            .where(EventInvitation.id == invitation_id)
            .options(*_INVITATION_DETAILS)
        )
        return await self.session.scalar(stmt)

    async def list_for_user(
        self, user_id: int, *, status: InvitationStatus | None = None
    ) -> Sequence[EventInvitation]:
        # Приглашения, полученные пользователем
        stmt = (
            select(EventInvitation)
            .where(EventInvitation.invitee_id == user_id)
            .options(*_INVITATION_DETAILS)
            .order_by(EventInvitation.id)
        )
        if status is not None:
            stmt = stmt.where(EventInvitation.status == status)
        return (await self.session.scalars(stmt)).all()
