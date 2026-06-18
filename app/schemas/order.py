from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .base import SchemaBase
from .book import BookRead
from typing import List


class OrderItemCreate(SchemaBase):
    book_id: UUID
    quantity: int = 1


class OrderCreate(SchemaBase):
    items: list[OrderItemCreate]


class OrderItemRead(SchemaBase):
    id: UUID
    book_id: UUID
    quantity: int
    unit_price: Decimal
    book: BookRead


class OrderRead(SchemaBase):
    id: UUID
    user_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime
    items: List[OrderItemRead] = []

