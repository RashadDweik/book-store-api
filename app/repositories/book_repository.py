"""Book repository for database access operations."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.author import Author
from app.models.book import Book


class BookRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    def _base_select(self):
        return select(Book).options(selectinload(Book.authors), selectinload(Book.category))

    async def get_by_id(self, book_id: UUID) -> Book | None:
        # Retrieve a book by UUID, returning None when missing.
        result = await self._db.execute(self._base_select().where(Book.id == book_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        query: str | None = None,
        author_id: UUID | None = None,
        category_id: UUID | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        min_release_date: "date" | None = None,
        max_release_date: "date" | None = None,
        in_stock: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by=None,
    ) -> list[Book]:
        # List books with optional filters and pagination.
        stmt = self._base_select()
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(or_(Book.title.ilike(pattern), Book.isbn.ilike(pattern)))
        if author_id is not None:
            stmt = stmt.where(Book.authors.any(Author.id == author_id))
        if category_id is not None:
            stmt = stmt.where(Book.category_id == category_id)
        if min_price is not None:
            stmt = stmt.where(Book.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Book.price <= max_price)
        if min_release_date is not None:
            stmt = stmt.where(Book.release_date >= min_release_date)
        if max_release_date is not None:
            stmt = stmt.where(Book.release_date <= max_release_date)
        if in_stock is True:
            stmt = stmt.where(Book.stock > 0)
        elif in_stock is False:
            stmt = stmt.where(Book.stock <= 0)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def create(self, book_data: dict, authors: list[Author]) -> Book:
        # Persist a new book with authors.
        book = Book(**book_data)
        book.authors = authors
        self._db.add(book)
        await self._db.flush()
        await self._db.refresh(book)
        return book

    async def update(
        self,
        book: Book,
        update_data: dict,
        authors: list[Author] | None = None,
    ) -> Book:
        # Apply updates to a book and refresh state.
        for key, value in update_data.items():
            setattr(book, key, value)
        if authors is not None:
            book.authors = authors
        self._db.add(book)
        await self._db.flush()
        await self._db.refresh(book)
        return book

    async def delete(self, book: Book) -> None:
        # Remove a book from persistence.
        await self._db.delete(book)
        await self._db.flush()
