"""Book catalog routes."""

from contextlib import suppress
from decimal import Decimal
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request , Response, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.inventory_cache import InventoryCache
from app.core.realtime import WebSocketHub
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


def _get_inventory_cache(request: Request) -> InventoryCache | None:
    return getattr(request.app.state, "inventory_cache", None)


def _get_websocket_hub(request: Request) -> WebSocketHub | None:
    return getattr(request.app.state, "websocket_hub", None)


async def _hydrate_book_stock(request: Request, books) -> None:
    cache = _get_inventory_cache(request)
    if cache is None:
        return
    with suppress(RedisError):
        if isinstance(books, list):
            await cache.hydrate_books(books)
        else:
            await cache.hydrate_book(books)


async def _store_book_stock(request: Request, book) -> None:
    cache = _get_inventory_cache(request)
    if cache is not None:
        with suppress(RedisError):
            await cache.set_stock(book.id, book.stock)

    hub = _get_websocket_hub(request)
    if hub is not None:
        await hub.broadcast(
            {
                "type": "book.stock.updated",
                "book_id": str(book.id),
                "stock": book.stock,
            }
        )


async def _delete_book_stock(request: Request, book_id: UUID) -> None:
    cache = _get_inventory_cache(request)
    if cache is not None:
        with suppress(RedisError):
            await cache.delete_stock(book_id)

    hub = _get_websocket_hub(request)
    if hub is not None:
        await hub.broadcast(
            {
                "type": "book.stock.deleted",
                "book_id": str(book_id),
            }
        )


@router.get("", response_model=list[BookRead])
async def list_books(
    request: Request,
    response: Response,
    q: str | None = Query(None, min_length=1, max_length=200),
    author_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    min_release_date: date | None = Query(None),
    max_release_date: date | None = Query(None),
    in_stock: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str | None = Query(None),
    service: BookService = Depends(get_book_service),
) -> list[BookRead]:
    # Destructure the result; count is now always returned
    books, total_count = await service.list_books(
        query=q, author_id=author_id, category_id=category_id,
        min_price=min_price, max_price=max_price,
        min_release_date=min_release_date, max_release_date=max_release_date,
        in_stock=in_stock, limit=limit, offset=offset, sort=sort
    )
    
    # Set the mandatory header
    response.headers["X-Total-Count"] = str(total_count)

    await _hydrate_book_stock(request, books)
    return books


@router.get("/{book_id}", response_model=BookRead)
async def read_book(
    book_id: UUID,
    request: Request,
    service: BookService = Depends(get_book_service),
) -> BookRead:
    # Return details for a single book.
    book = await service.get_book(book_id)
    await _hydrate_book_stock(request, book)
    return book


@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_book(
    data: BookCreate,
    request: Request,
    service: BookService = Depends(get_book_service),
) -> BookRead:
    # Create a new book entry.
    book = await service.create_book(data)
    await _store_book_stock(request, book)
    return book


@router.patch(
    "/{book_id}",
    response_model=BookRead,
    dependencies=[Depends(require_admin)],
)
async def update_book(
    book_id: UUID,
    data: BookUpdate,
    request: Request,
    service: BookService = Depends(get_book_service),
) -> BookRead:
    # Update a book entry.
    book = await service.update_book(book_id, data)
    await _store_book_stock(request, book)
    return book


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_book(
    book_id: UUID,
    request: Request,
    service: BookService = Depends(get_book_service),
) -> None:
    # Delete a book entry.
    await service.delete_book(book_id)
    await _delete_book_stock(request, book_id)
    return None
