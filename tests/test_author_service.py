from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from app.repositories.author_repository import AuthorRepository
from app.schemas.author import AuthorCreate, AuthorUpdate
from app.services.author_service import AuthorService


pytestmark = pytest.mark.anyio


async def test_list_authors_calls_repository() -> None:
    repo = AsyncMock(spec=AuthorRepository)
    repo.list = AsyncMock(return_value=[SimpleNamespace(id=uuid4())])
    service = AuthorService(repo)

    result = await service.list_authors(query="name", limit=5, offset=10)

    assert result == repo.list.return_value
    repo.list.assert_awaited_once_with(query="name", limit=5, offset=10)


async def test_get_author_missing_raises() -> None:
    repo = AsyncMock(spec=AuthorRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    service = AuthorService(repo)

    with pytest.raises(HTTPException) as exc:
        await service.get_author(uuid4())

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_create_author_returns_created() -> None:
    repo = AsyncMock(spec=AuthorRepository)
    author = SimpleNamespace(id=uuid4())
    repo.create = AsyncMock(return_value=author)
    repo.get_by_id = AsyncMock(return_value=author)
    service = AuthorService(repo)

    result = await service.create_author(AuthorCreate(name="Author", bio="Bio"))

    assert result is author
    repo.create.assert_awaited_once()


async def test_update_author_returns_existing_when_no_changes() -> None:
    repo = AsyncMock(spec=AuthorRepository)
    author = SimpleNamespace(id=uuid4())
    repo.get_by_id = AsyncMock(return_value=author)
    repo.update = AsyncMock()
    service = AuthorService(repo)

    result = await service.update_author(author.id, AuthorUpdate())

    assert result is author
    repo.update.assert_not_awaited()


async def test_delete_author_calls_repository() -> None:
    repo = AsyncMock(spec=AuthorRepository)
    author = SimpleNamespace(id=uuid4())
    repo.get_by_id = AsyncMock(return_value=author)
    repo.delete = AsyncMock()
    service = AuthorService(repo)

    await service.delete_author(author.id)

    repo.delete.assert_awaited_once_with(author)
