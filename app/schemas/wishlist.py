from datetime import datetime
from uuid import UUID

from pydantic import Field

from .base import SchemaBase
from .book import BookRead


class WishlistItemCreate(SchemaBase):
    book_id: UUID


class WishlistItemRead(SchemaBase):
    id: UUID
    created_at: datetime
    book: BookRead


class WishlistRead(SchemaBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    items: list[WishlistItemRead] = Field(default_factory=list)
