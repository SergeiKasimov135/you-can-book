from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Booking,
    EventInvitation,
    Friendship,
    FriendshipStatus,
    InvitationStatus,
    User,
)
from app.repositories import BookingRepository, FriendshipRepository, InvitationRepository, UserRepository
from app.services.booking_service import BookingService
from app.services.exceptions import (
    AlreadyExistsError,
    BusinessRuleError,
    NotFoundError,
    PermissionDeniedError,
)


class FriendService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.friendships = FriendshipRepository(session)
        self.invitations = InvitationRepository(session)
        self.bookings = BookingRepository(session)
        self.booking_service = BookingService(session)

    # ---------- Заявки в друзья ----------
    async def send_request(self, actor: User, friend_id: int) -> Friendship:
        if friend_id == actor.id:
            raise BusinessRuleError("Нельзя добавить в друзья самого себя")
        if await self.users.get(friend_id) is None:
            raise NotFoundError(f"Пользователь {friend_id} не найден")

        existing = await self.friendships.get_between(actor.id, friend_id)
        if existing is not None:
            if existing.status == FriendshipStatus.ACCEPTED:
                raise AlreadyExistsError("Вы уже друзья")
            if existing.requester_id == actor.id:
                raise AlreadyExistsError("Заявка уже отправлена, ждём ответа")
            # Встречная заявка — сразу принимаем
            return await self.accept_request(existing.id, actor)

        try:
            # SAVEPOINT: при ошибке откатывается только эта вставка
            async with self.session.begin_nested():
                friendship = await self.friendships.create(requester_id=actor.id, addressee_id=friend_id)
        except IntegrityError as exc:  # ux_friendships_pair: гонка двух встречных заявок
            raise AlreadyExistsError("Заявка между этими пользователями уже существует") from exc
        await self.session.commit()
        return friendship

    async def _get_incoming(self, request_id: int, actor: User) -> Friendship:
        friendship = await self.friendships.get(request_id)
        if friendship is None or friendship.status != FriendshipStatus.PENDING:
            raise NotFoundError(f"Заявка {request_id} не найдена")
        if friendship.addressee_id != actor.id:
            raise PermissionDeniedError("Ответить на заявку может только тот, кому она отправлена")
        return friendship

    async def accept_request(self, request_id: int, actor: User) -> Friendship:
        friendship = await self._get_incoming(request_id, actor)
        await self.friendships.update(friendship, status=FriendshipStatus.ACCEPTED)
        await self.session.commit()
        return friendship

    async def decline_request(self, request_id: int, actor: User) -> None:
        # Отклонённая заявка удаляется, её можно отправить снова
        await self.friendships.delete(await self._get_incoming(request_id, actor))
        await self.session.commit()

    async def remove_friend(self, actor: User, friend_id: int) -> None:
        friendship = await self.friendships.get_between(actor.id, friend_id)
        if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
            raise NotFoundError("Этот пользователь не в списке друзей")
        await self.friendships.delete(friendship)
        await self.session.commit()

    async def list_friends(self, user_id: int) -> Sequence[User]:
        return await self.friendships.list_friends(user_id)

    async def list_incoming_requests(self, user_id: int) -> Sequence[Friendship]:
        return await self.friendships.list_incoming(user_id)

    async def friends_going(self, user_id: int, event_id: int) -> Sequence[User]:
        # Кто из друзей уже идёт на мероприятие
        return await self.friendships.friends_going(user_id, event_id)

    # ---------- Приглашения на мероприятия ----------
    async def invite(
        self, actor: User, friend_id: int, event_id: int, message: str | None = None
    ) -> EventInvitation:
        if not await self.friendships.are_friends(actor.id, friend_id):
            raise BusinessRuleError("Пригласить можно только друга")
        if await self.bookings.get_active(friend_id, event_id):
            raise BusinessRuleError("Друг уже записан на это мероприятие")
        # Мероприятие не отменено и не прошло
        await self.booking_service.check_bookable(friend_id, event_id)
        try:
            async with self.session.begin_nested():  # SAVEPOINT, см. send_request
                invitation = await self.invitations.create(
                    event_id=event_id, inviter_id=actor.id, invitee_id=friend_id, message=message
                )
        except IntegrityError as exc:  # uq_event_invitations_triple
            raise AlreadyExistsError("Вы уже приглашали этого друга на это мероприятие") from exc
        await self.session.commit()
        return await self.get_invitation(invitation.id)

    async def get_invitation(self, invitation_id: int) -> EventInvitation:
        invitation = await self.invitations.get_with_details(invitation_id)
        if invitation is None:
            raise NotFoundError(f"Приглашение {invitation_id} не найдено")
        return invitation

    async def list_invitations(
        self, user_id: int, status: InvitationStatus | None = None
    ) -> Sequence[EventInvitation]:
        return await self.invitations.list_for_user(user_id, status=status)

    async def respond(
        self, invitation_id: int, actor: User, accept: bool
    ) -> tuple[EventInvitation, Booking | None]:
        invitation = await self.get_invitation(invitation_id)
        if invitation.invitee_id != actor.id:
            raise PermissionDeniedError("Ответить на приглашение может только приглашённый")
        if invitation.status != InvitationStatus.PENDING:
            raise BusinessRuleError(f"На приглашение уже ответили: {invitation.status.value}")

        booking = None
        if accept:
            await self.booking_service.check_bookable(actor.id, invitation.event_id)
            booking = await self.bookings.create(
                user_id=actor.id,
                event_id=invitation.event_id,
                comment=f"По приглашению: {invitation.inviter.full_name}",
            )
        await self.invitations.update(
            invitation, status=InvitationStatus.ACCEPTED if accept else InvitationStatus.DECLINED
        )
        await self.session.commit()
        return invitation, booking
