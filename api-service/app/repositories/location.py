from app.models import Location
from app.repositories.base import BaseRepository


class LocationRepository(BaseRepository[Location]):
    model = Location
