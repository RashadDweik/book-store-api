from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.models.book import Book
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository
from app.schemas.cart import CartItemCreate, CartItemUpdate
from app.services.cart_service import CartService


pytestmark = pytest.mark.anyio


async def test_get_cart_creates_missing_cart() -> None:
    repo = AsyncMock(spec=CartRepository)
    repo.get_by_user_id = AsyncMock(return_value=None)
    created = SimpleNamespace(id=uuid4())
    repo.create = AsyncMock(return_value=created)
    books = AsyncMock(spec=BookRepository)
    service = CartService(repo, books)

    result = await service.get_cart(uuid4())

    assert result is created
    repo.create.assert_awaited_once()


async def test_add_item_uses_authenticated_user_cart_only() -> None:
    user_id = uuid4()
    other_user_id = uuid4()
    cart = SimpleNamespace(id=uuid4(), user_id=user_id)
    repo = AsyncMock(spec=CartRepository)
    repo.get_by_user_id = AsyncMock(return_value=cart)
    repo.get_item_by_book = AsyncMock(return_value=None)
    repo.add_item = AsyncMock()
    books = AsyncMock(spec=BookRepository)
    books.get_by_id = AsyncMock(return_value=Book(title="Book", price=Decimal("10.00"), stock=1))
    service = CartService(repo, books)

    await service.add_item(
        user_id,
        CartItemCreate(book_id=uuid4(), quantity=1),
    )

    repo.get_by_user_id.assert_any_await(user_id)
    assert repo.get_by_user_id.await_count == 2
    assert all(call.args[0] == user_id for call in repo.get_by_user_id.await_args_list)
    assert other_user_id != user_id


async def test_add_item_rejects_missing_book() -> None:
    repo = AsyncMock(spec=CartRepository)
    repo.get_by_user_id = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    books = AsyncMock(spec=BookRepository)
    books.get_by_id = AsyncMock(return_value=None)
    service = CartService(repo, books)

    with pytest.raises(HTTPException) as exc:
        await service.add_item(uuid4(), CartItemCreate(book_id=uuid4(), quantity=1))

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    repo.add_item.assert_not_awaited()


async def test_add_item_increments_existing_quantity() -> None:
    cart_id = uuid4()
    user_id = uuid4()
    book_id = uuid4()
    cart = SimpleNamespace(id=cart_id, user_id=user_id)
    existing = SimpleNamespace(quantity=2)
    repo = AsyncMock(spec=CartRepository)
    repo.get_by_user_id = AsyncMock(side_effect=[cart, cart])
    repo.get_item_by_book = AsyncMock(return_value=existing)
    repo.update_item = AsyncMock(return_value=existing)
    books = AsyncMock(spec=BookRepository)
    books.get_by_id = AsyncMock(return_value=Book(title="Book", price=Decimal("10.00"), stock=1))
    service = CartService(repo, books)

    result = await service.add_item(user_id, CartItemCreate(book_id=book_id, quantity=3))

    assert result is cart
    repo.update_item.assert_awaited_once_with(existing, 5)


async def test_update_item_rejects_missing_item() -> None:
    repo = AsyncMock(spec=CartRepository)
    cart = SimpleNamespace(id=uuid4())
    repo.get_by_user_id = AsyncMock(return_value=cart)
    repo.get_item_by_id = AsyncMock(return_value=None)
    books = AsyncMock(spec=BookRepository)
    service = CartService(repo, books)

    with pytest.raises(HTTPException) as exc:
        await service.update_item(uuid4(), uuid4(), CartItemUpdate(quantity=2))

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_update_item_rejects_invalid_quantity() -> None:
    repo = AsyncMock(spec=CartRepository)
    cart = SimpleNamespace(id=uuid4())
    item = SimpleNamespace(quantity=1)
    repo.get_by_user_id = AsyncMock(return_value=cart)
    repo.get_item_by_id = AsyncMock(return_value=item)
    books = AsyncMock(spec=BookRepository)
    service = CartService(repo, books)

    with pytest.raises(HTTPException) as exc:
        await service.update_item(uuid4(), uuid4(), CartItemUpdate(quantity=0))

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_remove_item_calls_repository() -> None:
    repo = AsyncMock(spec=CartRepository)
    cart = SimpleNamespace(id=uuid4())
    item = SimpleNamespace(id=uuid4())
    repo.get_by_user_id = AsyncMock(return_value=cart)
    repo.get_item_by_id = AsyncMock(return_value=item)
    repo.delete_item = AsyncMock()
    books = AsyncMock(spec=BookRepository)
    service = CartService(repo, books)

    result = await service.remove_item(uuid4(), item.id)

    assert result is cart
    repo.delete_item.assert_awaited_once_with(item)