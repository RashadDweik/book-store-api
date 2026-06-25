"""Order repository for database access operations."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload , joinedload

from app.models.book import Book
from app.models.order import Order, OrderItem


class OrderRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    def _base_select(self):
        return select(Order).options(
            selectinload(Order.items).options(
                joinedload(OrderItem.book).options(
                    selectinload(Book.authors),
                    joinedload(Book.category)
                )
            )
        )

    async def get_by_id(self, order_id: UUID) -> Order | None:
        # Retrieve an order by id with its items and book details.
        result = await self._db.execute(self._base_select().where(Order.id == order_id))
        return result.scalar_one_or_none()

    async def list_by_user_id(self, user_id: UUID) -> list[Order]:
        # Return all orders for a user, newest first.
        result = await self._db.execute(
            self._base_select()
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
        )
        return result.scalars().all()

    async def create(
        self,
        *,
        user_id: UUID,
        items: list[OrderItem],
        total_amount: Decimal,
        status: str = "placed",
    ) -> Order:
        # Persist an order and its items in one flush.
        order = Order(user_id=user_id, status=status, total_amount=total_amount, items=items)
        self._db.add(order)
        await self._db.flush()
        return await self.get_by_id(order.id) or order

    async def update(self, order: Order, update_data: dict) -> Order:
        # Apply updates to an order and refresh state.
        for key, value in update_data.items():
            setattr(order, key, value)
        self._db.add(order)
        await self._db.flush()
        await self._db.refresh(order)
        return order