"""Order and checkout routes."""

from uuid import UUID

from contextlib import suppress
from fastapi import Request
from redis.exceptions import RedisError

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderRead
from app.services.order_service import OrderService


router = APIRouter(prefix="/orders", tags=["Orders"])


def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    # Build a service with the request-scoped database session.
    return OrderService(OrderRepository(db), CartRepository(db), BookRepository(db))


@router.post("/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def checkout(
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    request: Request = None,
) -> OrderRead:
    # Place an order from the authenticated user's cart.
    order = await service.checkout(current_user.id)

    # After checkout, update inventory cache and broadcast stock updates.
    cache = getattr(request.app.state, "inventory_cache", None) if request is not None else None
    hub = getattr(request.app.state, "websocket_hub", None) if request is not None else None
    for item in getattr(order, "items", []) or []:
        book = getattr(item, "book", None)
        if book is None:
            continue
        # Fetch fresh book state from the repository to avoid stale cache-hydration values.
        fresh = await service._books.get_by_id(book.id)
        if fresh is None:
            continue
        if cache is not None:
            with suppress(RedisError):
                await cache.set_stock(fresh.id, fresh.stock)

        if hub is not None:
            await hub.broadcast(
                {
                    "type": "book.stock.updated",
                    "book_id": str(fresh.id),
                    "stock": fresh.stock,
                }
            )

    return order


@router.get("", response_model=list[OrderRead])
async def list_orders(
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> list[OrderRead]:
    # Return the authenticated user's order history.
    return await service.list_orders(current_user.id)


@router.get("/{order_id}", response_model=OrderRead)
async def read_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRead:
    # Return a single order when it belongs to the authenticated user.
    return await service.get_order(current_user.id, order_id)


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    request: Request = None,
) -> OrderRead:
    # Allow the authenticated user to cancel their order when allowed.
    order = await service.cancel_order(current_user.id, order_id)

    cache = getattr(request.app.state, "inventory_cache", None) if request is not None else None
    hub = getattr(request.app.state, "websocket_hub", None) if request is not None else None

    for item in getattr(order, "items", []) or []:
        fresh = await service._books.get_by_id(item.book_id)
        if fresh is None:
            continue
        if cache is not None:
            with suppress(RedisError):
                await cache.set_stock(fresh.id, fresh.stock)

        if hub is not None:
            await hub.broadcast(
                {
                    "type": "book.stock.updated",
                    "book_id": str(fresh.id),
                    "stock": fresh.stock,
                }
            )

    return order
    