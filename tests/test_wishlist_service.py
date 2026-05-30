from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.models.book import Book
from app.repositories.book_repository import BookRepository
from app.repositories.wishlist_repository import WishlistRepository
from app.schemas.wishlist import WishlistItemCreate
from app.services.wishlist_service import WishlistService


pytestmark = pytest.mark.anyio


async def test_get_wishlist_creates_missing_wishlist() -> None:
    repo = AsyncMock(spec=WishlistRepository)
    repo.get_by_user_id = AsyncMock(return_value=None)
    created = SimpleNamespace(id=uuid4())
    repo.create = AsyncMock(return_value=created)
    books = AsyncMock(spec=BookRepository)
    service = WishlistService(repo, books)

    result = await service.get_wishlist(uuid4())

    assert result is created
    repo.create.assert_awaited_once()


async def test_add_item_uses_authenticated_user_wishlist_only() -> None:
    user_id = uuid4()
    other_user_id = uuid4()
    wishlist = SimpleNamespace(id=uuid4(), user_id=user_id)
    repo = AsyncMock(spec=WishlistRepository)
    repo.get_by_user_id = AsyncMock(return_value=wishlist)
    repo.get_item_by_book = AsyncMock(return_value=None)
    repo.add_item = AsyncMock()
    books = AsyncMock(spec=BookRepository)
    books.get_by_id = AsyncMock(return_value=Book(title="Book", price=Decimal("10.00"), stock=1))
    service = WishlistService(repo, books)

    await service.add_item(
        user_id,
        WishlistItemCreate(book_id=uuid4()),
    )

    repo.get_by_user_id.assert_any_await(user_id)
    assert repo.get_by_user_id.await_count == 2
    assert all(call.args[0] == user_id for call in repo.get_by_user_id.await_args_list)
    assert other_user_id != user_id


async def test_add_item_rejects_missing_book() -> None:
    repo = AsyncMock(spec=WishlistRepository)
    repo.get_by_user_id = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    books = AsyncMock(spec=BookRepository)
    books.get_by_id = AsyncMock(return_value=None)
    service = WishlistService(repo, books)

    with pytest.raises(HTTPException) as exc:
        await service.add_item(uuid4(), WishlistItemCreate(book_id=uuid4()))

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    repo.add_item.assert_not_awaited()


async def test_add_item_skips_duplicate_book() -> None:
    wishlist_id = uuid4()
    user_id = uuid4()
    book_id = uuid4()
    wishlist = SimpleNamespace(id=wishlist_id, user_id=user_id)
    existing = SimpleNamespace(id=uuid4(), book_id=book_id)
    repo = AsyncMock(spec=WishlistRepository)
    repo.get_by_user_id = AsyncMock(side_effect=[wishlist, wishlist])
    repo.get_item_by_book = AsyncMock(return_value=existing)
    books = AsyncMock(spec=BookRepository)
    books.get_by_id = AsyncMock(return_value=Book(title="Book", price=Decimal("10.00"), stock=1))
    service = WishlistService(repo, books)

    result = await service.add_item(user_id, WishlistItemCreate(book_id=book_id))

    assert result is wishlist
    repo.add_item.assert_not_awaited()


async def test_remove_item_rejects_missing_item() -> None:
    repo = AsyncMock(spec=WishlistRepository)
    wishlist = SimpleNamespace(id=uuid4())
    repo.get_by_user_id = AsyncMock(return_value=wishlist)
    repo.get_item_by_id = AsyncMock(return_value=None)
    books = AsyncMock(spec=BookRepository)
    service = WishlistService(repo, books)

    with pytest.raises(HTTPException) as exc:
        await service.remove_item(uuid4(), uuid4())

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_remove_item_calls_repository() -> None:
    repo = AsyncMock(spec=WishlistRepository)
    wishlist = SimpleNamespace(id=uuid4())
    item = SimpleNamespace(id=uuid4())
    repo.get_by_user_id = AsyncMock(return_value=wishlist)
    repo.get_item_by_id = AsyncMock(return_value=item)
    repo.delete_item = AsyncMock()
    books = AsyncMock(spec=BookRepository)
    service = WishlistService(repo, books)

    result = await service.remove_item(uuid4(), item.id)

    assert result is wishlist
    repo.delete_item.assert_awaited_once_with(item)