from datetime import datetime
from uuid import UUID
from app.schemas.book import BookRead
from .base import SchemaBase


class CartItemBase(SchemaBase):
    book_id: UUID
    quantity: int = 1


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(SchemaBase):
    quantity: int | None = None


class CartItemRead(SchemaBase):
    id: UUID
    quantity: int
    created_at: datetime
    book: BookRead


class CartRead(SchemaBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    items: list[CartItemRead] = []
