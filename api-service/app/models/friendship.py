from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.enums import FriendshipStatus, InvitationStatus, varchar_enum

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.user import User


class Friendship(CreatedAtMixin, Base):
    # Дружба — связь M:N «пользователь — пользователь»

    __tablename__ = "friendships"
    __table_args__ = (CheckConstraint("requester_id <> addressee_id", name="not_self"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[FriendshipStatus] = mapped_column(
        varchar_enum(FriendshipStatus, "status"),
        default=FriendshipStatus.PENDING,
        server_default=FriendshipStatus.PENDING.value,
    )

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id])
    addressee: Mapped["User"] = relationship(foreign_keys=[addressee_id])


# Одна дружба на пару: (1 -> 2) и (2 -> 1) считаются одной строкой
Index(
    "ux_friendships_pair",
    func.least(Friendship.requester_id, Friendship.addressee_id),
    func.greatest(Friendship.requester_id, Friendship.addressee_id),
    unique=True,
)


class EventInvitation(CreatedAtMixin, Base):
    # Приглашение друга на мероприятие

    __tablename__ = "event_invitations"
    __table_args__ = (
        CheckConstraint("inviter_id <> invitee_id", name="not_self"),
        # Один раз на (мероприятие, кто, кого)
        UniqueConstraint("event_id", "inviter_id", "invitee_id", name="uq_event_invitations_triple"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[InvitationStatus] = mapped_column(
        varchar_enum(InvitationStatus, "status"),
        default=InvitationStatus.PENDING,
        server_default=InvitationStatus.PENDING.value,
    )
    message: Mapped[str | None] = mapped_column(String(255))

    event: Mapped["Event"] = relationship()
    inviter: Mapped["User"] = relationship(foreign_keys=[inviter_id])
    invitee: Mapped["User"] = relationship(foreign_keys=[invitee_id])
