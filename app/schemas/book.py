from datetime import datetime
from decimal import Decimal

from .author import AuthorSummary
from .base import SchemaBase


class BookBase(SchemaBase):
    title: str
    price: Decimal
    description: str | None = None
    isbn: str | None = None
    stock: int = 0


class BookCreate(BookBase):
    author_ids: list[int]


class BookUpdate(SchemaBase):
    title: str | None = None
    price: Decimal | None = None
    description: str | None = None
    isbn: str | None = None
    stock: int | None = None
    author_ids: list[int] | None = None


class BookRead(BookBase):
    id: int
    created_at: datetime
    authors: list[AuthorSummary] = []
