from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.wishlist import Wishlist, WishlistItem
from app.repositories.wishlist_repository import WishlistRepository


pytestmark = pytest.mark.anyio


async def test_get_by_user_id_returns_wishlist() -> None:
    wishlist = Wishlist(user_id=uuid4())
    result = Mock()
    result.scalar_one_or_none.return_value = wishlist
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = WishlistRepository(db)

    fetched = await repo.get_by_user_id(wishlist.user_id)

    assert fetched is wishlist
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_create_persists_wishlist() -> None:
    user_id = uuid4()
    wishlist = Wishlist(user_id=user_id)
    result = Mock()
    result.scalar_one.return_value = wishlist
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    repo = WishlistRepository(db)

    created = await repo.create(user_id)

    assert isinstance(created, Wishlist)
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    db.execute.assert_awaited_once()
    result.scalar_one.assert_called_once()


async def test_add_item_persists_wishlist_item() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = WishlistRepository(db)
    wishlist = Wishlist(user_id=uuid4())

    created = await repo.add_item(wishlist, uuid4())

    assert isinstance(created, WishlistItem)
    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)


async def test_delete_item_removes_item() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    repo = WishlistRepository(db)
    item = WishlistItem(wishlist_id=uuid4(), book_id=uuid4())

    await repo.delete_item(item)

    db.delete.assert_awaited_once_with(item)
    db.flush.assert_awaited_once()


async def test_clear_items_removes_all_wishlist_items() -> None:
    item = WishlistItem(wishlist_id=uuid4(), book_id=uuid4())
    result = Mock()
    scalars = Mock()
    scalars.all.return_value = [item]
    result.scalars.return_value = scalars
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    repo = WishlistRepository(db)
    wishlist = Wishlist(user_id=uuid4())
    wishlist.id = uuid4()

    await repo.clear_items(wishlist)

    db.delete.assert_awaited_once_with(item)
    db.flush.assert_awaited_once()


async def test_get_item_by_book_returns_existing_item() -> None:
    item = WishlistItem(wishlist_id=uuid4(), book_id=uuid4())
    result = Mock()
    result.scalar_one_or_none.return_value = item
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = WishlistRepository(db)

    fetched = await repo.get_item_by_book(item.wishlist_id, item.book_id)

    assert fetched is item


async def test_get_item_by_id_returns_existing_item() -> None:
    item = WishlistItem(wishlist_id=uuid4(), book_id=uuid4())
    result = Mock()
    result.scalar_one_or_none.return_value = item
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = WishlistRepository(db)

    fetched = await repo.get_item_by_id(item.wishlist_id, item.id)

    assert fetched is item