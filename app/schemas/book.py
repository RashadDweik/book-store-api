from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import computed_field

from .author import AuthorSummary
from .base import SchemaBase


def build_openlibrary_cover_url(isbn: str, size: str = "M") -> str:
    normalized_isbn = isbn.replace("-", "").strip()
    return f"https://covers.openlibrary.org/b/isbn/{normalized_isbn}-{size}.jpg"


class BookBase(SchemaBase):
    title: str
    price: Decimal
    release_date: date | None = None
    description: str | None = None
    isbn: str | None = None
    stock: int = 0


class BookCreate(BookBase):
    author_ids: list[UUID]


class BookUpdate(SchemaBase):
    title: str | None = None
    price: Decimal | None = None
    description: str | None = None
    isbn: str | None = None
    stock: int | None = None
    author_ids: list[UUID] | None = None


class BookRead(BookBase):
    id: UUID
    created_at: datetime
    authors: list[AuthorSummary] = []

    @computed_field
    @property
    def cover_url(self) -> str | None:
        if not self.isbn:
            return None
        return build_openlibrary_cover_url(self.isbn)
