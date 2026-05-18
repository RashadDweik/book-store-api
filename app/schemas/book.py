from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .author import AuthorSummary
from .base import SchemaBase


class BookBase(SchemaBase):
    title: str
    price: Decimal
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
