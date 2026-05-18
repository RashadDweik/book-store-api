from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel

if TYPE_CHECKING:
    from .book import Book


# Association table for the many-to-many relationship between books and authors.
book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", UUID(as_uuid=True), ForeignKey("books.id"), primary_key=True),
    Column("author_id", UUID(as_uuid=True), ForeignKey("authors.id"), primary_key=True),
)


class Author(BaseModel):
    __tablename__ = "authors"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    books: Mapped[list["Book"]] = relationship(
        "Book",
        secondary=book_authors,
        back_populates="authors",
    )
