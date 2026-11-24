from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.event import Event


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (CheckConstraint("capacity > 0", name="capacity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(255))
    capacity: Mapped[int | None] = mapped_column(Integer)  # справочно, не контролируется

    # Площадку с мероприятиями удалить нельзя (RESTRICT)
    events: Mapped[list["Event"]] = relationship(back_populates="location", passive_deletes="all")
