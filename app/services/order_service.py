"""Order service that encapsulates checkout and order history logic."""

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status

from app.models.order import Order, OrderItem
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository


class OrderService:
    def __init__(self, orders: OrderRepository, carts: CartRepository, books: BookRepository) -> None:
        # Store repositories used for persistence and lookups.
        self._orders = orders
        self._carts = carts
        self._books = books

    async def checkout(self, user_id: UUID) -> Order:
        # Convert the current cart into a placed order and clear the cart.
        cart = await self._carts.get_by_user_id(user_id)
        if cart is None or not cart.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty.",
            )

        order_items: list[OrderItem] = []
        total_amount = Decimal("0.00")

        for cart_item in cart.items:
            if cart_item.quantity < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cart items must have a quantity of at least 1.",
                )

            book = await self._books.get_by_id_for_update(cart_item.book_id)
            if book is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Book not found.",
                )

            if book.stock < cart_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Not enough stock for "{book.title}".',
                )

            book.stock -= cart_item.quantity
            await self._books.update(book, {"stock": book.stock})

            order_items.append(
                OrderItem(
                    book_id=book.id,
                    quantity=cart_item.quantity,
                    unit_price=book.price,
                )
            )
            total_amount += Decimal(book.price) * cart_item.quantity

        order = await self._orders.create(
            status="placed",
            user_id=user_id,
            items=order_items,
            total_amount=total_amount,
        )

        await self._carts.clear_items(cart)
        return order

    async def list_orders(self, user_id: UUID) -> list[Order]:
        # Return the authenticated user's order history.
        return await self._orders.list_by_user_id(user_id)

    async def get_order(self, user_id: UUID, order_id: UUID) -> Order:
        # Return a single order only when it belongs to the authenticated user.
        order = await self._orders.get_by_id(order_id)
        if order is None or order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )
        return order

    async def cancel_order(self, user_id: UUID, order_id: UUID) -> Order:
        # Allow users to cancel orders that are still cancellable and restock items.
        order = await self._orders.get_by_id(order_id)
        if order is None or order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found.",
            )

        # Only allow cancellation for orders that haven't progressed past placement.
        if order.status not in ("pending", "placed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order cannot be cancelled at this stage.",
            )

        # Restock items and update status.
        for item in order.items:
            # Lock the book row and increment stock.
            book = await self._books.get_by_id_for_update(item.book_id)
            if book is None:
                # If the book is missing, continue; cancellation should still proceed.
                continue
            book.stock = (book.stock or 0) + item.quantity
            await self._books.update(book, {"stock": book.stock})

        order = await self._orders.update(order, {"status": "cancelled"})
        return order