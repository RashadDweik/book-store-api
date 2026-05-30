"""Book service that encapsulates book domain logic."""

from decimal import Decimal
from uuid import UUID
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.book import Book
from app.repositories.author_repository import AuthorRepository
from app.repositories.book_repository import BookRepository
from app.repositories.category_repository import CategoryRepository
from app.schemas.book import BookCreate, BookUpdate


class BookService:
    def __init__(
        self,
        repo: BookRepository,
        authors: AuthorRepository,
        categories: CategoryRepository,
    ) -> None:
        # Store repositories used for persistence and lookups.
        self._repo = repo
        self._authors = authors
        self._categories = categories

    @staticmethod
    def _is_isbn_unique_violation(error: IntegrityError) -> bool:
        """Return True when IntegrityError is due to books.isbn uniqueness."""
        constraint_name = getattr(getattr(error, "orig", None), "constraint_name", None)
        if constraint_name == "uq_books_isbn":
            return True

        diag = getattr(getattr(error, "orig", None), "diag", None)
        if diag is not None and getattr(diag, "constraint_name", None) == "uq_books_isbn":
            return True

        message = str(getattr(error, "orig", error)).lower()
        if "uq_books_isbn" in message:
            return True
        if "books.isbn" in message and "unique" in message:
            return True
        if "key (isbn)" in message and "already exists" in message:
            return True
        return False

    def _resolve_sort(self, sort: str | None):
        if not sort:
            return Book.created_at.desc()
        descending = sort.startswith("-")
        key = sort[1:] if descending else sort
        columns = {
            "title": Book.title,
            "price": Book.price,
            "created_at": Book.created_at,
        }
        column = columns.get(key)
        if column is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort field.",
            )
        return column.desc() if descending else column.asc()

    async def _resolve_authors(self, author_ids: list[UUID]) -> list:
        if not author_ids:
            return []
        unique_ids = list(dict.fromkeys(author_ids))
        authors = await self._authors.get_by_ids(unique_ids)
        found = {author.id for author in authors}
        missing = [str(author_id) for author_id in unique_ids if author_id not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Authors not found: {', '.join(missing)}.",
            )
        return authors

    async def _resolve_category(self, category_id: UUID | None) -> None:
        if category_id is None:
            return
        category = await self._categories.get_by_id(category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found.",
            )

    @staticmethod
    def _validate_price_range(
        min_price: Decimal | None,
        max_price: Decimal | None,
    ) -> None:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price cannot be greater than max_price.",
            )

    @staticmethod
    def _validate_release_date_range(
        min_release_date: date | None,
        max_release_date: date | None,
    ) -> None:
        if (
            min_release_date is not None
            and max_release_date is not None
            and min_release_date > max_release_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_release_date cannot be greater than max_release_date.",
            )

    async def list_books(
        self,
        *,
        query: str | None = None,
        author_id: UUID | None = None,
        category_id: UUID | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        min_release_date: date | None = None,
        max_release_date: date | None = None,
        in_stock: bool | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str | None = None,
    ) -> list[Book]:
        # Validate filters and return the paged book list.
        self._validate_price_range(min_price, max_price)
        self._validate_release_date_range(min_release_date, max_release_date)
        order_by = self._resolve_sort(sort)
        return await self._repo.list(
            query=query,
            author_id=author_id,
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            min_release_date=min_release_date,
            max_release_date=max_release_date,
            in_stock=in_stock,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )

    async def get_book(self, book_id: UUID) -> Book:
        # Return a book or raise when missing.
        book = await self._repo.get_by_id(book_id)
        if book is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )
        return book

    async def create_book(self, data: BookCreate) -> Book:
        # Create a book with authors and enforce ISBN uniqueness.
        authors = await self._resolve_authors(data.author_ids)
        await self._resolve_category(data.category_id)
        payload = data.model_dump()
        payload.pop("author_ids", None)
        try:
            created = await self._repo.create(payload, authors)
        except IntegrityError as exc:
            if self._is_isbn_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ISBN already exists.",
                ) from exc
            raise
        reloaded = await self._repo.get_by_id(created.id)
        return reloaded or created

    async def update_book(self, book_id: UUID, data: BookUpdate) -> Book:
        # Update a book and optionally replace authors.
        book = await self._repo.get_by_id(book_id)
        if book is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )

        update_data = data.model_dump(exclude_unset=True)
        author_ids = update_data.pop("author_ids", None)
        authors = None
        if author_ids is not None:
            authors = await self._resolve_authors(author_ids)
        await self._resolve_category(update_data.get("category_id"))

        if not update_data and authors is None:
            return book

        try:
            updated = await self._repo.update(book, update_data, authors)
        except IntegrityError as exc:
            if self._is_isbn_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ISBN already exists.",
                ) from exc
            raise
        reloaded = await self._repo.get_by_id(updated.id)
        return reloaded or updated

    async def delete_book(self, book_id: UUID) -> None:
        # Remove a book if it exists.
        book = await self._repo.get_by_id(book_id)
        if book is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )
        await self._repo.delete(book)
