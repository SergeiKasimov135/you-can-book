from fastapi import APIRouter, status

from app.api.deps import AdminUser, Bookings, CurrentUser
from app.models import BookingStatus, UserRole
from app.schemas.bookings import BookingCreate, BookingOut
from app.services import PermissionDeniedError
from app.services.permissions import can_manage_event

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def book(data: BookingCreate, user: CurrentUser, bookings: Bookings):
    return await bookings.book(user.id, data.event_id, data.comment)


@router.get("", response_model=list[BookingOut])
async def my_bookings(user: CurrentUser, bookings: Bookings):
    return await bookings.list_my(user.id)


@router.get("/all", response_model=list[BookingOut])
async def all_bookings(
    _: AdminUser,
    bookings: Bookings,
    user_id: int | None = None,
    event_id: int | None = None,
    status: BookingStatus | None = None,
):
    return await bookings.list_for_admin(user_id=user_id, event_id=event_id, status=status)


@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(booking_id: int, user: CurrentUser, bookings: Bookings):
    booking = await bookings.get(booking_id)
    # Бронь видят владелец, организатор мероприятия и администратор
    if booking.user_id != user.id and user.role != UserRole.ADMIN and not can_manage_event(user, booking.event):
        raise PermissionDeniedError("Это чужая бронь")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(booking_id: int, user: CurrentUser, bookings: Bookings):
    return await bookings.cancel(booking_id, user)


@router.post("/{booking_id}/attend", response_model=BookingOut)
async def mark_attended(booking_id: int, user: CurrentUser, bookings: Bookings):
    return await bookings.mark_attended(booking_id, user)
