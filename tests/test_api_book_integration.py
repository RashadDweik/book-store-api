import os
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, status

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test-secret"

from app.api.v1.routers import books as books_router
from app.core.dependencies import require_admin
from app.main import create_app


pytestmark = pytest.mark.anyio


class StubBookService:
    def __init__(
        self,
        *,
        book: SimpleNamespace,
        books: list[SimpleNamespace] | None = None,
        updated_book: SimpleNamespace | None = None,
        list_error: Exception | None = None,
        get_error: Exception | None = None,
        create_error: Exception | None = None,
        update_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self._book = book
        self._books = books or [book]
        self._updated_book = updated_book or book
        self._list_error = list_error
        self._get_error = get_error
        self._create_error = create_error
        self._update_error = update_error
        self._delete_error = delete_error

    async def list_books(self, **_kwargs) -> list[SimpleNamespace]:
        if self._list_error:
            raise self._list_error
        return self._books

    async def get_book(self, _book_id) -> SimpleNamespace:
        if self._get_error:
            raise self._get_error
        return self._book

    async def create_book(self, _data) -> SimpleNamespace:
        if self._create_error:
            raise self._create_error
        return self._book

    async def update_book(self, _book_id, _data) -> SimpleNamespace:
        if self._update_error:
            raise self._update_error
        return self._updated_book

    async def delete_book(self, _book_id) -> None:
        if self._delete_error:
            raise self._delete_error
        return None


def build_book(**overrides) -> SimpleNamespace:
    author = SimpleNamespace(id=uuid4(), name="Author")
    payload = {
        "id": uuid4(),
        "title": "Test Book",
        "price": Decimal("19.99"),
        "description": "Desc",
        "isbn": "0735235902",
        "stock": 10,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "authors": [author],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.fixture
def app() -> FastAPI:
    app = create_app()
    yield app
    app.dependency_overrides.clear()


def override_services(app: FastAPI, service: StubBookService, admin: bool = False) -> None:
    app.dependency_overrides[books_router.get_book_service] = lambda: service
    if admin:
        app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=uuid4())


async def test_list_books_returns_books(app: FastAPI) -> None:
    book = build_book()
    service = StubBookService(book=book, books=[book])
    override_services(app, service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/books")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(book.id)
    assert body[0]["title"] == book.title
    assert str(body[0]["price"]) == str(book.price)
    assert body[0]["cover_url"] == "https://covers.openlibrary.org/b/isbn/0735235902-M.jpg"
    assert body[0]["authors"][0]["id"] == str(book.authors[0].id)


async def test_read_book_returns_book(app: FastAPI) -> None:
    book = build_book()
    service = StubBookService(book=book)
    override_services(app, service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/books/{book.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(book.id)
    assert body["title"] == book.title
    assert body["cover_url"] == "https://covers.openlibrary.org/b/isbn/0735235902-M.jpg"


async def test_create_book_requires_admin(app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/books",
            json={
                "title": "Book",
                "price": 10.0,
                "author_ids": [str(uuid4())],
            },
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_create_book_returns_book(app: FastAPI) -> None:
    book = build_book()
    service = StubBookService(book=book)
    override_services(app, service, admin=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/books",
            json={
                "title": book.title,
                "price": float(book.price),
                "author_ids": [str(book.authors[0].id)],
            },
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(book.id)


async def test_update_book_returns_book(app: FastAPI) -> None:
    book = build_book()
    updated = build_book(id=book.id, title="Updated")
    service = StubBookService(book=book, updated_book=updated)
    override_services(app, service, admin=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            f"/api/v1/books/{book.id}",
            json={"title": "Updated"},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


async def test_delete_book_returns_204(app: FastAPI) -> None:
    book = build_book()
    service = StubBookService(book=book)
    override_services(app, service, admin=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.delete(f"/api/v1/books/{book.id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
