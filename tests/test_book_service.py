from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.repositories.author_repository import AuthorRepository
from app.repositories.book_repository import BookRepository
from app.repositories.category_repository import CategoryRepository
from app.schemas.book import BookCreate, BookUpdate
from app.services.book_service import BookService


pytestmark = pytest.mark.anyio


class DummyUniqueViolationError(Exception):
    def __init__(self, message: str, constraint_name: str | None = None) -> None:
        super().__init__(message)
        self.constraint_name = constraint_name


async def test_list_books_rejects_invalid_price_range() -> None:
    repo = AsyncMock(spec=BookRepository)
    authors = AsyncMock(spec=AuthorRepository)
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)

    with pytest.raises(HTTPException) as exc:
        await service.list_books(min_price=Decimal("10"), max_price=Decimal("5"))

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    repo.list.assert_not_awaited()


async def test_list_books_rejects_invalid_sort() -> None:
    repo = AsyncMock(spec=BookRepository)
    authors = AsyncMock(spec=AuthorRepository)
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)

    with pytest.raises(HTTPException) as exc:
        await service.list_books(sort="invalid")

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    repo.list.assert_not_awaited()


async def test_list_books_calls_repository() -> None:
    repo = AsyncMock(spec=BookRepository)
    repo.list = AsyncMock(return_value=[SimpleNamespace(id=uuid4())])
    authors = AsyncMock(spec=AuthorRepository)
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)

    result = await service.list_books(query="fast", limit=5, offset=10, sort="title")

    assert result == repo.list.return_value
    repo.list.assert_awaited_once()
    kwargs = repo.list.call_args.kwargs
    assert kwargs["query"] == "fast"
    assert kwargs["limit"] == 5
    assert kwargs["offset"] == 10
    assert kwargs["order_by"] is not None


async def test_get_book_missing_raises() -> None:
    repo = AsyncMock(spec=BookRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    authors = AsyncMock(spec=AuthorRepository)
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)

    with pytest.raises(HTTPException) as exc:
        await service.get_book(uuid4())

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_create_book_rejects_missing_authors() -> None:
    repo = AsyncMock(spec=BookRepository)
    repo.create = AsyncMock()
    authors = AsyncMock(spec=AuthorRepository)
    authors.get_by_ids = AsyncMock(return_value=[])
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)
    author_id = uuid4()

    with pytest.raises(HTTPException) as exc:
        await service.create_book(
            BookCreate(
                title="Book",
                price=Decimal("10.00"),
                release_date=date(2024, 1, 1),
                author_ids=[author_id],
            )
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    repo.create.assert_not_awaited()


async def test_create_book_rejects_missing_category() -> None:
    repo = AsyncMock(spec=BookRepository)
    repo.create = AsyncMock()
    authors = AsyncMock(spec=AuthorRepository)
    authors.get_by_ids = AsyncMock(return_value=[])
    categories = AsyncMock(spec=CategoryRepository)
    categories.get_by_id = AsyncMock(return_value=None)
    service = BookService(repo, authors, categories)
    category_id = uuid4()

    with pytest.raises(HTTPException) as exc:
        await service.create_book(
            BookCreate(
                title="Book",
                price=Decimal("10.00"),
                release_date=date(2024, 1, 1),
                category_id=category_id,
                author_ids=[],
            )
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "Category not found."
    repo.create.assert_not_awaited()


async def test_create_book_maps_isbn_unique_error() -> None:
    repo = AsyncMock(spec=BookRepository)
    authors = AsyncMock(spec=AuthorRepository)
    author_id = uuid4()
    authors.get_by_ids = AsyncMock(return_value=[SimpleNamespace(id=author_id)])
    categories = AsyncMock(spec=CategoryRepository)
    integrity_error = IntegrityError(
        "INSERT INTO books (...) VALUES (...)",
        {},
        DummyUniqueViolationError(
            'duplicate key value violates unique constraint "uq_books_isbn"',
            constraint_name="uq_books_isbn",
        ),
    )
    repo.create = AsyncMock(side_effect=integrity_error)
    service = BookService(repo, authors, categories)

    with pytest.raises(HTTPException) as exc:
        await service.create_book(
            BookCreate(
                title="Book",
                price=Decimal("10.00"),
                release_date=date(2024, 1, 1),
                author_ids=[author_id],
                isbn="978-1-4028-9999-1",
            )
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "ISBN already exists."


async def test_update_book_returns_existing_when_no_changes() -> None:
    repo = AsyncMock(spec=BookRepository)
    book = SimpleNamespace(id=uuid4())
    repo.get_by_id = AsyncMock(return_value=book)
    repo.update = AsyncMock()
    authors = AsyncMock(spec=AuthorRepository)
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)

    result = await service.update_book(book.id, BookUpdate())

    assert result is book
    repo.update.assert_not_awaited()


async def test_update_book_replaces_authors() -> None:
    repo = AsyncMock(spec=BookRepository)
    book = SimpleNamespace(id=uuid4())
    updated = SimpleNamespace(id=uuid4())
    repo.get_by_id = AsyncMock(side_effect=[book, updated])
    repo.update = AsyncMock(return_value=updated)
    authors = AsyncMock(spec=AuthorRepository)
    author = SimpleNamespace(id=uuid4())
    authors.get_by_ids = AsyncMock(return_value=[author])
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)

    result = await service.update_book(book.id, BookUpdate(author_ids=[author.id]))

    assert result is updated
    repo.update.assert_awaited_once_with(book, {}, [author])


async def test_delete_book_calls_repository() -> None:
    repo = AsyncMock(spec=BookRepository)
    book = SimpleNamespace(id=uuid4())
    repo.get_by_id = AsyncMock(return_value=book)
    repo.delete = AsyncMock()
    authors = AsyncMock(spec=AuthorRepository)
    categories = AsyncMock(spec=CategoryRepository)
    service = BookService(repo, authors, categories)

    await service.delete_book(book.id)

    repo.delete.assert_awaited_once_with(book)
