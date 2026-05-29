from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.category import Category
from app.repositories.category_repository import CategoryRepository


pytestmark = pytest.mark.anyio


async def test_get_by_id_returns_category() -> None:
    category = Category(name="Fiction")
    result = Mock()
    result.scalar_one_or_none.return_value = category
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = CategoryRepository(db)

    fetched = await repo.get_by_id(uuid4())

    assert fetched is category
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_list_returns_categories() -> None:
    category = Category(name="Fiction")
    result = Mock()
    scalars = Mock()
    scalars.all.return_value = [category]
    result.scalars.return_value = scalars
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = CategoryRepository(db)

    categories = await repo.list(limit=10, offset=0)

    assert categories == [category]
    db.execute.assert_awaited_once()


async def test_create_persists_category() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = CategoryRepository(db)

    created = await repo.create({"name": "Fiction"})

    assert created.name == "Fiction"
    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)
