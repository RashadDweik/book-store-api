import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, status

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test-secret"

from app.api.v1.routers import categories as categories_router
from app.core.dependencies import require_admin
from app.main import create_app


pytestmark = pytest.mark.anyio


class StubCategoryService:
    def __init__(
        self,
        *,
        category: SimpleNamespace,
        categories: list[SimpleNamespace] | None = None,
        updated_category: SimpleNamespace | None = None,
        list_error: Exception | None = None,
        get_error: Exception | None = None,
        create_error: Exception | None = None,
        update_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self._category = category
        self._categories = categories or [category]
        self._updated_category = updated_category or category
        self._list_error = list_error
        self._get_error = get_error
        self._create_error = create_error
        self._update_error = update_error
        self._delete_error = delete_error

    async def list_categories(self, **_kwargs) -> list[SimpleNamespace]:
        if self._list_error:
            raise self._list_error
        return self._categories

    async def get_category(self, _category_id) -> SimpleNamespace:
        if self._get_error:
            raise self._get_error
        return self._category

    async def create_category(self, _data) -> SimpleNamespace:
        if self._create_error:
            raise self._create_error
        return self._category

    async def update_category(self, _category_id, _data) -> SimpleNamespace:
        if self._update_error:
            raise self._update_error
        return self._updated_category

    async def delete_category(self, _category_id) -> None:
        if self._delete_error:
            raise self._delete_error
        return None


def build_category(**overrides) -> SimpleNamespace:
    payload = {
        "id": uuid4(),
        "name": "Fiction",
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.fixture
def app() -> FastAPI:
    app = create_app()
    yield app
    app.dependency_overrides.clear()


def override_services(app: FastAPI, service: StubCategoryService, admin: bool = False) -> None:
    app.dependency_overrides[categories_router.get_category_service] = lambda: service
    if admin:
        app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=uuid4())


async def test_list_categories_returns_categories(app: FastAPI) -> None:
    category = build_category()
    service = StubCategoryService(category=category, categories=[category])
    override_services(app, service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/categories")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(category.id)
    assert body[0]["name"] == category.name


async def test_create_category_requires_admin(app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/categories", json={"name": "Fiction"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_create_category_returns_category(app: FastAPI) -> None:
    category = build_category()
    service = StubCategoryService(category=category)
    override_services(app, service, admin=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/categories", json={"name": category.name})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(category.id)


async def test_delete_category_returns_204(app: FastAPI) -> None:
    category = build_category()
    service = StubCategoryService(category=category)
    override_services(app, service, admin=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(f"/api/v1/categories/{category.id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT