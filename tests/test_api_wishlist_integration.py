import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, status

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test-secret"

from app.api.v1.routers import wishlist as wishlist_router
from app.core.dependencies import get_current_user
from app.main import create_app


pytestmark = pytest.mark.anyio


class StubWishlistService:
    def __init__(
        self,
        *,
        wishlist: SimpleNamespace,
        updated_wishlist: SimpleNamespace | None = None,
    ) -> None:
        self._wishlist = wishlist
        self._updated_wishlist = updated_wishlist or wishlist

    async def get_wishlist(self, _user_id) -> SimpleNamespace:
        return self._wishlist

    async def add_item(self, _user_id, _data) -> SimpleNamespace:
        return self._updated_wishlist

    async def remove_item(self, _user_id, _item_id) -> SimpleNamespace:
        return self._updated_wishlist

    async def clear_wishlist(self, _user_id) -> SimpleNamespace:
        return self._updated_wishlist


def build_wishlist(**overrides) -> SimpleNamespace:
    item = SimpleNamespace(
        id=uuid4(),
        book_id=uuid4(),
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    payload = {
        "id": uuid4(),
        "user_id": uuid4(),
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "items": [item],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.fixture
def app() -> FastAPI:
    app = create_app()
    yield app
    app.dependency_overrides.clear()


def override_services(
    app: FastAPI,
    service: StubWishlistService,
    current_user: SimpleNamespace | None = None,
) -> None:
    app.dependency_overrides[wishlist_router.get_wishlist_service] = lambda: service
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user


async def test_read_wishlist_returns_wishlist(app: FastAPI) -> None:
    wishlist = build_wishlist()
    service = StubWishlistService(wishlist=wishlist)
    current_user = SimpleNamespace(id=wishlist.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/wishlist")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(wishlist.id)
    assert body["items"][0]["id"] == str(wishlist.items[0].id)


async def test_add_wishlist_item_returns_wishlist(app: FastAPI) -> None:
    wishlist = build_wishlist()
    service = StubWishlistService(wishlist=wishlist)
    current_user = SimpleNamespace(id=wishlist.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/wishlist/items",
            json={"book_id": str(wishlist.items[0].book_id)},
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(wishlist.id)


async def test_delete_wishlist_item_returns_wishlist(app: FastAPI) -> None:
    wishlist = build_wishlist()
    service = StubWishlistService(wishlist=wishlist)
    current_user = SimpleNamespace(id=wishlist.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(f"/api/v1/wishlist/items/{wishlist.items[0].id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(wishlist.id)


async def test_clear_wishlist_returns_wishlist(app: FastAPI) -> None:
    wishlist = build_wishlist()
    service = StubWishlistService(wishlist=wishlist)
    current_user = SimpleNamespace(id=wishlist.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete("/api/v1/wishlist")

    assert response.status_code == 200
    assert response.json()["id"] == str(wishlist.id)