"""Book catalog routes."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.repositories.author_repository import AuthorRepository
from app.repositories.book_repository import BookRepository
from app.repositories.category_repository import CategoryRepository
from app.schemas.book import BookCreate, BookRead, BookUpdate
from app.services.book_service import BookService


# Group book catalog endpoints under the /books prefix.
router = APIRouter(prefix="/books", tags=["Books"])


def get_book_service(db: AsyncSession = Depends(get_db)) -> BookService:
    # Build a service with the request-scoped database session.
    return BookService(BookRepository(db), AuthorRepository(db), CategoryRepository(db))


@router.get("", response_model=list[BookRead])
async def list_books(
    q: str | None = Query(None, min_length=1, max_length=200),
    author_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    in_stock: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str | None = Query(
        None,
        description="Sort by title, price, or created_at. Use -field for descending.",
    ),
    service: BookService = Depends(get_book_service),
) -> list[BookRead]:
    # Return a filtered list of books.
    return await service.list_books(
        query=q,
        author_id=author_id,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        limit=limit,
        offset=offset,
        sort=sort,
    )


@router.get("/{book_id}", response_model=BookRead)
async def read_book(
    book_id: UUID,
    service: BookService = Depends(get_book_service),
) -> BookRead:
    # Return details for a single book.
    return await service.get_book(book_id)


@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_book(
    data: BookCreate,
    service: BookService = Depends(get_book_service),
) -> BookRead:
    # Create a new book entry.
    return await service.create_book(data)


@router.patch(
    "/{book_id}",
    response_model=BookRead,
    dependencies=[Depends(require_admin)],
)
async def update_book(
    book_id: UUID,
    data: BookUpdate,
    service: BookService = Depends(get_book_service),
) -> BookRead:
    # Update a book entry.
    return await service.update_book(book_id, data)


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_book(
    book_id: UUID,
    service: BookService = Depends(get_book_service),
) -> None:
    # Delete a book entry.
    await service.delete_book(book_id)
    return None
