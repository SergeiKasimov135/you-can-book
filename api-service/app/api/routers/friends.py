from fastapi import APIRouter, status

from app.api.deps import CurrentUser, Friends
from app.schemas.bookings import BookingOut, FriendRequestCreate, FriendRequestOut
from app.schemas.users import UserShort

router = APIRouter(prefix="/friends", tags=["friends"])


@router.get("", response_model=list[UserShort])
async def list_friends(user: CurrentUser, friends: Friends):
    return await friends.list_friends(user.id)


@router.get("/bookings", response_model=list[BookingOut])
async def friends_bookings(user: CurrentUser, friends: Friends):
    # Куда идут друзья: их брони на будущие мероприятия
    return await friends.friends_bookings(user.id)


@router.get("/requests", response_model=list[FriendRequestOut])
async def incoming_requests(user: CurrentUser, friends: Friends):
    return await friends.list_incoming_requests(user.id)


@router.post("/requests", response_model=FriendRequestOut, status_code=status.HTTP_201_CREATED)
async def send_request(data: FriendRequestCreate, user: CurrentUser, friends: Friends):
    # Если встречная заявка уже есть, дружба сразу становится ACCEPTED
    return await friends.send_request(user, data.user_id)


@router.post("/requests/{request_id}/accept", response_model=FriendRequestOut)
async def accept_request(request_id: int, user: CurrentUser, friends: Friends):
    return await friends.accept_request(request_id, user)


@router.post("/requests/{request_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_request(request_id: int, user: CurrentUser, friends: Friends):
    await friends.decline_request(request_id, user)


@router.delete("/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(friend_id: int, user: CurrentUser, friends: Friends):
    await friends.remove_friend(user, friend_id)
