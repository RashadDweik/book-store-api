from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import List, Optional

from .base import SchemaBase
from .book import BookRead


class BookRead(SchemaBase):
    id: UUID
    title: str
    price: Decimal
    cover_url: Optional[str] = None


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
