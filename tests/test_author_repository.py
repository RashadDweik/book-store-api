from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.author import Author
from app.repositories.author_repository import AuthorRepository


pytestmark = pytest.mark.anyio


async def test_get_by_id_returns_author() -> None:
    author = Author(name="Author", bio="Bio")
    result = Mock()
    result.scalar_one_or_none.return_value = author
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = AuthorRepository(db)

    fetched = await repo.get_by_id(uuid4())

    assert fetched is author
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_list_returns_authors() -> None:
    author = Author(name="Author", bio=None)
    result = Mock()
    scalars = Mock()
    scalars.all.return_value = [author]
    result.scalars.return_value = scalars
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = AuthorRepository(db)

    authors = await repo.list(limit=5, offset=0)

    assert authors == [author]
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_create_persists_author() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = AuthorRepository(db)
    payload = {"name": "New Author", "bio": "Bio"}

    created = await repo.create(payload)

    assert created.name == payload["name"]
    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)


async def test_update_applies_changes() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = AuthorRepository(db)
    author = Author(name="Old", bio=None)

    updated = await repo.update(author, {"name": "New"})

    assert updated is author
    assert author.name == "New"
    db.add.assert_called_once_with(author)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(author)


async def test_delete_removes_author() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    repo = AuthorRepository(db)
    author = Author(name="Delete", bio=None)

    await repo.delete(author)

    db.delete.assert_awaited_once_with(author)
    db.flush.assert_awaited_once()


async def test_get_by_ids_returns_matching_authors() -> None:
    author = Author(name="Author", bio=None)
    result = Mock()
    scalars = Mock()
    scalars.all.return_value = [author]
    result.scalars.return_value = scalars
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = AuthorRepository(db)

    authors = await repo.get_by_ids([uuid4()])

    assert authors == [author]
    db.execute.assert_awaited_once()
