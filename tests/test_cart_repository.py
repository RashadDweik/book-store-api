from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.cart import Cart, CartItem
from app.repositories.cart_repository import CartRepository


pytestmark = pytest.mark.anyio


async def test_get_by_user_id_returns_cart() -> None:
    cart = Cart(user_id=uuid4())
    result = Mock()
    result.scalar_one_or_none.return_value = cart
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = CartRepository(db)

    fetched = await repo.get_by_user_id(cart.user_id)

    assert fetched is cart
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_create_persists_cart() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    user_id = uuid4()
    cart = Cart(user_id=user_id)
    result = Mock()
    result.scalar_one.return_value = cart
    db.execute = AsyncMock(return_value=result)
    repo = CartRepository(db)

    created = await repo.create(user_id)

    assert isinstance(created, Cart)
    added_cart = db.add.call_args.args[0]
    assert isinstance(added_cart, Cart)
    assert added_cart.user_id == user_id
    db.flush.assert_awaited_once()
    db.execute.assert_awaited_once()


async def test_add_item_persists_cart_item() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = CartRepository(db)
    cart = Cart(user_id=uuid4())

    created = await repo.add_item(cart, uuid4(), 2)

    assert isinstance(created, CartItem)
    assert created.quantity == 2
    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)


async def test_update_item_applies_quantity() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = CartRepository(db)
    item = CartItem(cart_id=uuid4(), book_id=uuid4(), quantity=1)

    updated = await repo.update_item(item, 4)

    assert updated is item
    assert item.quantity == 4
    db.add.assert_called_once_with(item)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(item)


async def test_delete_item_removes_item() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    repo = CartRepository(db)
    item = CartItem(cart_id=uuid4(), book_id=uuid4(), quantity=1)

    await repo.delete_item(item)

    db.delete.assert_awaited_once_with(item)
    db.flush.assert_awaited_once()


async def test_clear_items_removes_all_cart_items() -> None:
    item = CartItem(cart_id=uuid4(), book_id=uuid4(), quantity=1)
    result = Mock()
    scalars = Mock()
    scalars.all.return_value = [item]
    result.scalars.return_value = scalars
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    repo = CartRepository(db)
    cart = Cart(user_id=uuid4())
    cart.id = uuid4()

    await repo.clear_items(cart)

    db.delete.assert_awaited_once_with(item)
    db.flush.assert_awaited_once()