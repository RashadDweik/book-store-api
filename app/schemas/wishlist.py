from datetime import datetime

from .base import SchemaBase


class WishlistItemCreate(SchemaBase):
    book_id: int


class WishlistItemRead(SchemaBase):
    id: int
    book_id: int
    created_at: datetime


class WishlistRead(SchemaBase):
    id: int
    user_id: int
    created_at: datetime
    items: list[WishlistItemRead] = []
