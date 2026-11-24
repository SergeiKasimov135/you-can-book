from fastapi import APIRouter, status

from app.api.deps import AdminUser, Catalog
from app.schemas.catalog import LocationCreate, LocationOut, LocationUpdate

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationOut])
async def list_locations(catalog: Catalog):
    return await catalog.list_locations()


@router.get("/{location_id}", response_model=LocationOut)
async def get_location(location_id: int, catalog: Catalog):
    return await catalog.get_location(location_id)


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
async def create_location(data: LocationCreate, admin: AdminUser, catalog: Catalog):
    return await catalog.create_location(admin, **data.model_dump())


@router.patch("/{location_id}", response_model=LocationOut)
async def update_location(location_id: int, data: LocationUpdate, admin: AdminUser, catalog: Catalog):
    # exclude_unset: меняются только поля, которые клиент прислал
    return await catalog.update_location(location_id, admin, **data.model_dump(exclude_unset=True))


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(location_id: int, admin: AdminUser, catalog: Catalog):
    await catalog.delete_location(location_id, admin)
