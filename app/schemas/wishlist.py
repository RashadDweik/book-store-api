from datetime import datetime
from uuid import UUID

from .base import SchemaBase


class WishlistItemCreate(SchemaBase):
    book_id: UUID


class WishlistItemRead(SchemaBase):
    id: UUID
    book_id: UUID
    created_at: datetime


class WishlistRead(SchemaBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    items: list[WishlistItemRead] = []
