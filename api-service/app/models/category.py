from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.event import event_categories

if TYPE_CHECKING:
    from app.models.event import Event


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)

    events: Mapped[list["Event"]] = relationship(
        secondary=event_categories, back_populates="categories", passive_deletes=True
    )
