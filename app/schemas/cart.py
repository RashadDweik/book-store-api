from datetime import datetime
from uuid import UUID

from .base import SchemaBase


class CartItemBase(SchemaBase):
    book_id: UUID
    quantity: int = 1


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(SchemaBase):
    quantity: int | None = None


class CartItemRead(CartItemBase):
    id: UUID


class CartRead(SchemaBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    items: list[CartItemRead] = []
