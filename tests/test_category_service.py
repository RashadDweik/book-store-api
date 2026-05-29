from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category_service import CategoryService


pytestmark = pytest.mark.anyio


async def test_list_categories_calls_repository() -> None:
    repo = AsyncMock(spec=CategoryRepository)
    repo.list = AsyncMock(return_value=[SimpleNamespace(id=uuid4())])
    service = CategoryService(repo)

    result = await service.list_categories(query="fic", limit=5, offset=10)

    assert result == repo.list.return_value
    repo.list.assert_awaited_once_with(query="fic", limit=5, offset=10)


async def test_get_category_missing_raises() -> None:
    repo = AsyncMock(spec=CategoryRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    service = CategoryService(repo)

    with pytest.raises(HTTPException) as exc:
        await service.get_category(uuid4())

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_create_category_returns_created() -> None:
    repo = AsyncMock(spec=CategoryRepository)
    category = SimpleNamespace(id=uuid4())
    repo.create = AsyncMock(return_value=category)
    repo.get_by_id = AsyncMock(return_value=category)
    service = CategoryService(repo)

    result = await service.create_category(CategoryCreate(name="Fiction"))

    assert result is category
    repo.create.assert_awaited_once()


async def test_update_category_returns_existing_when_no_changes() -> None:
    repo = AsyncMock(spec=CategoryRepository)
    category = SimpleNamespace(id=uuid4())
    repo.get_by_id = AsyncMock(return_value=category)
    repo.update = AsyncMock()
    service = CategoryService(repo)

    result = await service.update_category(category.id, CategoryUpdate())

    assert result is category
    repo.update.assert_not_awaited()


async def test_delete_category_calls_repository() -> None:
    repo = AsyncMock(spec=CategoryRepository)
    category = SimpleNamespace(id=uuid4())
    repo.get_by_id = AsyncMock(return_value=category)
    repo.delete = AsyncMock()
    service = CategoryService(repo)

    await service.delete_category(category.id)

    repo.delete.assert_awaited_once_with(category)