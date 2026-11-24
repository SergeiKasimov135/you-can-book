from fastapi import APIRouter, status

from app.api.deps import AdminUser, Users
from app.models import UserRole
from app.schemas.users import RoleUpdate, UserOut

# Управление пользователями — только администратор
router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(_: AdminUser, users: Users, role: UserRole | None = None):
    return await users.list(role)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, _: AdminUser, users: Users):
    return await users.get(user_id)


@router.patch("/{user_id}/role", response_model=UserOut)
async def change_role(user_id: int, data: RoleUpdate, admin: AdminUser, users: Users):
    return await users.change_role(user_id, data.role, admin)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, _: AdminUser, users: Users):
    await users.delete(user_id)
