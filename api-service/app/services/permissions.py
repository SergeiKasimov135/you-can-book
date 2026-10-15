from app.models import Event, User, UserRole
from app.services.exceptions import PermissionDeniedError


def require_admin(actor: User) -> None:
    if actor.role != UserRole.ADMIN:
        raise PermissionDeniedError("Действие доступно только администратору")


def require_organizer(actor: User) -> None:
    # Создавать мероприятия могут организаторы и администраторы
    if actor.role not in (UserRole.ORGANIZER, UserRole.ADMIN):
        raise PermissionDeniedError("Создавать мероприятия может только организатор")


def can_manage_event(actor: User, event: Event) -> bool:
    return actor.role == UserRole.ADMIN or (
        actor.role == UserRole.ORGANIZER and event.organizer_id == actor.id
    )


def require_event_manager(actor: User, event: Event) -> None:
    if not can_manage_event(actor, event):
        raise PermissionDeniedError("Управлять мероприятием может только его организатор или администратор")
