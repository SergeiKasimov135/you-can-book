from fastapi import APIRouter, status

from app.api.deps import AdminUser, Catalog
from app.schemas.catalog import CategoryCreate, CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(catalog: Catalog):
    return await catalog.list_categories()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, admin: AdminUser, catalog: Catalog):
    return await catalog.create_category(admin, data.name)


@router.patch("/{category_id}", response_model=CategoryOut)
async def rename_category(category_id: int, data: CategoryCreate, admin: AdminUser, catalog: Catalog):
    return await catalog.rename_category(category_id, admin, data.name)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, admin: AdminUser, catalog: Catalog):
    await catalog.delete_category(category_id, admin)
