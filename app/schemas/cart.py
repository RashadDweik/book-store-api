from datetime import datetime

from .base import SchemaBase


class CartItemBase(SchemaBase):
    book_id: int
    quantity: int = 1


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(SchemaBase):
    quantity: int | None = None


class CartItemRead(CartItemBase):
    id: int


class CartRead(SchemaBase):
    id: int
    user_id: int
    created_at: datetime
    items: list[CartItemRead] = []
