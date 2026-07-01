from datetime import date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.author import Author
from app.models.book import Book
from app.repositories.book_repository import BookRepository


pytestmark = pytest.mark.anyio


async def test_get_by_id_returns_book() -> None:
    book = Book(title="Test", price=Decimal("10.00"), release_date=date(2024, 1, 15), stock=5)
    result = Mock()
    result.scalar_one_or_none.return_value = book
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = BookRepository(db)

    fetched = await repo.get_by_id(uuid4())

    assert fetched is book
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_list_returns_books() -> None:
    book = Book(id=uuid4(), title="Test", price=Decimal("10.00"), release_date=date(2024, 1, 15), stock=5)
    
    # 1. Mock for the COUNT result
    count_result = Mock()
    count_result.scalar.return_value = 1  # The count query returns 1
    
    # 2. Mock for the DATA result
    data_result = Mock()
    data_result.scalars.return_value.all.return_value = [book]
    
    db = AsyncMock(spec=AsyncSession)
    # 3. Use side_effect to return mocks in order
    db.execute.side_effect = [count_result, data_result]
    
    repo = BookRepository(db)

    (books, count) = await repo.list(limit=10, offset=0)
    
    # Now count will be 1 (an int), not a Mock object
    assert books == [book]
    assert count == 1
    
    # Verify the database was called twice
    assert db.execute.call_count == 2


async def test_create_persists_book() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = BookRepository(db)
    authors = [Author(name="Author", bio=None)]
    payload = {
        "title": "New Book",
        "price": Decimal("12.50"),
        "release_date": date(2024, 2, 1),
        "description": "Desc",
        "isbn": "978-1-4028-1234-5",
        "stock": 3,
    }

    created = await repo.create(payload, authors)

    assert created.title == payload["title"]
    assert created.authors == authors
    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)


async def test_update_applies_changes_and_authors() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = BookRepository(db)
    book = Book(title="Old", price=Decimal("9.50"), release_date=date(2024, 1, 1), stock=1)
    authors = [Author(name="Updated", bio=None)]

    updated = await repo.update(book, {"title": "New", "release_date": date(2024, 3, 1)}, authors)

    assert updated is book
    assert book.title == "New"
    assert book.release_date == date(2024, 3, 1)
    assert book.authors == authors
    db.add.assert_called_once_with(book)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(book)


async def test_delete_removes_book() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    repo = BookRepository(db)
    book = Book(title="Delete", price=Decimal("8.00"), release_date=date(2024, 4, 1), stock=2)

    await repo.delete(book)

    db.delete.assert_awaited_once_with(book)
    db.flush.assert_awaited_once()
