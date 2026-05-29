from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .book import Book


class Category(BaseModel):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # A category can contain many books; books point back via category_id.
    books: Mapped[list["Book"]] = relationship(
        "Book",
        back_populates="category",
    )