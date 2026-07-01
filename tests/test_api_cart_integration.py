import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from pydantic.types import Decimal

import httpx
import pytest
from fastapi import FastAPI, status

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test-secret"

from app.api.v1.routers import cart as cart_router
from app.core.dependencies import get_current_user
from app.main import create_app


pytestmark = pytest.mark.anyio


def build_book_nested():
    return SimpleNamespace(
        id=str(uuid4()), 
        title="The Great Gatsby",
        price=Decimal("19.99"),  # Pydantic expects Decimal or float
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    )


class StubCartService:
    def __init__(
        self,
        *,
        cart: SimpleNamespace,
        updated_cart: SimpleNamespace | None = None,
    ) -> None:
        self._cart = cart
        self._updated_cart = updated_cart or cart

    async def get_cart(self, _user_id) -> SimpleNamespace:
        return self._cart

    async def add_item(self, _user_id, _data) -> SimpleNamespace:
        return self._updated_cart

    async def update_item(self, _user_id, _item_id, _data) -> SimpleNamespace:
        return self._updated_cart

    async def remove_item(self, _user_id, _item_id) -> SimpleNamespace:
        return self._updated_cart

    async def clear_cart(self, _user_id) -> SimpleNamespace:
        return self._updated_cart


def build_cart(**overrides) -> SimpleNamespace:
    
    book=build_book_nested()

    item = SimpleNamespace(
        id=uuid4(),
        book_id=uuid4(),
        quantity=2,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        book=book
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


def override_services(app: FastAPI, service: StubCartService, current_user: SimpleNamespace | None = None) -> None:
    app.dependency_overrides[cart_router.get_cart_service] = lambda: service
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user


async def test_read_cart_returns_cart(app: FastAPI) -> None:
    cart = build_cart()
    service = StubCartService(cart=cart)
    current_user = SimpleNamespace(id=cart.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/cart")

    assert response.status_code == 200
    body = response.json()
    
    # Assertions
    assert body["id"] == str(cart.id)
    assert body["items"][0]["id"] == str(cart.items[0].id)
    assert body["items"][0]["book"]["title"] == "The Great Gatsby"

    # Check the actual value (19.99), and verify if it arrives as a float or string
    # Usually, it's safer to compare as a float or str to be safe against rounding
    assert float(body["items"][0]["book"]["price"]) == 19.99 

    api_date = body["items"][0]["book"]["created_at"].replace("Z", "+00:00")
    stub_date = cart.items[0].book.created_at.replace("Z", "+00:00")
    
    assert api_date == stub_date
   

async def test_add_cart_item_returns_cart(app: FastAPI) -> None:
    cart = build_cart()
    service = StubCartService(cart=cart)
    current_user = SimpleNamespace(id=cart.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/cart/items",
            json={"book_id": str(cart.items[0].book_id), "quantity": 2},
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(cart.id)


async def test_update_cart_item_returns_cart(app: FastAPI) -> None:
    cart = build_cart()
    service = StubCartService(cart=cart)
    current_user = SimpleNamespace(id=cart.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/v1/cart/items/{cart.items[0].id}",
            json={"quantity": 5},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(cart.id)


async def test_delete_cart_item_returns_cart(app: FastAPI) -> None:
    cart = build_cart()
    service = StubCartService(cart=cart)
    current_user = SimpleNamespace(id=cart.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(f"/api/v1/cart/items/{cart.items[0].id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(cart.id)


async def test_clear_cart_returns_cart(app: FastAPI) -> None:
    cart = build_cart()
    service = StubCartService(cart=cart)
    current_user = SimpleNamespace(id=cart.user_id)
    override_services(app, service, current_user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete("/api/v1/cart")

    assert response.status_code == 200
    assert response.json()["id"] == str(cart.id)