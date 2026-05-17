from datetime import datetime
from decimal import Decimal

from .base import SchemaBase


class OrderItemCreate(SchemaBase):
    book_id: int
    quantity: int = 1


class OrderCreate(SchemaBase):
    items: list[OrderItemCreate]


class OrderItemRead(SchemaBase):
    id: int
    book_id: int
    quantity: int
    unit_price: Decimal


class OrderRead(SchemaBase):
    id: int
    user_id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    items: list[OrderItemRead] = []
