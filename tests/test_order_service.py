from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.models.book import Book
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.services.order_service import OrderService


pytestmark = pytest.mark.anyio


async def test_checkout_rejects_empty_cart() -> None:
    orders = AsyncMock(spec=OrderRepository)
    carts = AsyncMock(spec=CartRepository)
    carts.get_by_user_id = AsyncMock(return_value=None)
    books = AsyncMock(spec=BookRepository)
    service = OrderService(orders, carts, books)

    with pytest.raises(HTTPException) as exc:
        await service.checkout(uuid4())

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "Cart is empty."


async def test_checkout_creates_order_and_clears_cart() -> None:
    user_id = uuid4()
    book_id = uuid4()
    cart = SimpleNamespace(
        id=uuid4(),
        items=[
            SimpleNamespace(
                id=uuid4(),
                book_id=book_id,
                quantity=2,
            )
        ],
    )
    book = Book(title="Book", price=Decimal("12.50"), stock=5)
    book.id = book_id

    orders = AsyncMock(spec=OrderRepository)
    created_order = SimpleNamespace(id=uuid4(), user_id=user_id, items=[])
    orders.create = AsyncMock(return_value=created_order)

    carts = AsyncMock(spec=CartRepository)
    carts.get_by_user_id = AsyncMock(return_value=cart)
    carts.clear_items = AsyncMock()

    books = AsyncMock(spec=BookRepository)
    books.get_by_id_for_update = AsyncMock(return_value=book)
    books.update = AsyncMock(return_value=book)

    service = OrderService(orders, carts, books)

    result = await service.checkout(user_id)

    assert result is created_order
    orders.create.assert_awaited_once()
    carts.clear_items.assert_awaited_once_with(cart)
    books.update.assert_awaited_once_with(book, {"stock": 3})


async def test_cancel_restocks_and_updates_order() -> None:
    user_id = uuid4()
    book_id = uuid4()
    order_id = uuid4()
    order = SimpleNamespace(
        id=order_id,
        user_id=user_id,
        items=[SimpleNamespace(book_id=book_id, quantity=2)],
        status="placed",
    )

    updated_order = SimpleNamespace(id=order_id, user_id=user_id, items=order.items, status="cancelled")

    orders = AsyncMock(spec=OrderRepository)
    orders.get_by_id = AsyncMock(return_value=order)
    orders.update = AsyncMock(return_value=updated_order)

    book = Book(title="Book", price=Decimal("12.50"), stock=3)
    book.id = book_id

    books = AsyncMock(spec=BookRepository)
    books.get_by_id_for_update = AsyncMock(return_value=book)
    books.update = AsyncMock(return_value=book)

    carts = AsyncMock(spec=CartRepository)

    service = OrderService(orders, carts, books)

    result = await service.cancel_order(user_id, order_id)

    books.update.assert_awaited_once_with(book, {"stock": 5})
    orders.update.assert_awaited_once_with(order, {"status": "cancelled"})
    assert result is updated_order


async def test_cancel_rejects_non_owner() -> None:
    user_id = uuid4()
    other_id = uuid4()
    order = SimpleNamespace(id=uuid4(), user_id=other_id, items=[], status="placed")

    orders = AsyncMock(spec=OrderRepository)
    orders.get_by_id = AsyncMock(return_value=order)
    books = AsyncMock(spec=BookRepository)
    carts = AsyncMock(spec=CartRepository)
    service = OrderService(orders, carts, books)

    with pytest.raises(HTTPException) as exc:
        await service.cancel_order(user_id, order.id)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_cancel_rejects_when_not_cancellable() -> None:
    user_id = uuid4()
    order = SimpleNamespace(id=uuid4(), user_id=user_id, items=[], status="shipped")

    orders = AsyncMock(spec=OrderRepository)
    orders.get_by_id = AsyncMock(return_value=order)
    books = AsyncMock(spec=BookRepository)
    carts = AsyncMock(spec=CartRepository)
    service = OrderService(orders, carts, books)

    with pytest.raises(HTTPException) as exc:
        await service.cancel_order(user_id, order.id)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_checkout_rejects_insufficient_stock() -> None:
    user_id = uuid4()
    book_id = uuid4()
    cart = SimpleNamespace(
        id=uuid4(),
        items=[SimpleNamespace(id=uuid4(), book_id=book_id, quantity=4)],
    )
    book = Book(title="Book", price=Decimal("12.50"), stock=3)
    book.id = book_id

    orders = AsyncMock(spec=OrderRepository)
    carts = AsyncMock(spec=CartRepository)
    carts.get_by_user_id = AsyncMock(return_value=cart)
    books = AsyncMock(spec=BookRepository)
    books.get_by_id_for_update = AsyncMock(return_value=book)
    service = OrderService(orders, carts, books)

    with pytest.raises(HTTPException) as exc:
        await service.checkout(user_id)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Not enough stock" in exc.value.detail
    carts.clear_items.assert_not_awaited()
