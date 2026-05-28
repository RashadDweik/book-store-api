"""Shopping cart routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartRead
from app.services.cart_service import CartService


# Group cart endpoints under the /cart prefix.
router = APIRouter(prefix="/cart", tags=["Cart"])


def get_cart_service(db: AsyncSession = Depends(get_db)) -> CartService:
    # Build a service with the request-scoped database session.
    return CartService(CartRepository(db), BookRepository(db))


@router.get("", response_model=CartRead)
async def read_cart(
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
) -> CartRead:
    # Return the authenticated user's cart.
    return await service.get_cart(current_user.id)


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    data: CartItemCreate,
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
) -> CartRead:
    # Add a book to the authenticated user's cart.
    return await service.add_item(current_user.id, data)


@router.patch("/items/{item_id}", response_model=CartRead)
async def update_cart_item(
    item_id: UUID,
    data: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
) -> CartRead:
    # Update the quantity of a cart item.
    return await service.update_item(current_user.id, item_id, data)


@router.delete("/items/{item_id}", response_model=CartRead)
async def delete_cart_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
) -> CartRead:
    # Remove a cart item from the authenticated user's cart.
    return await service.remove_item(current_user.id, item_id)


@router.delete("", response_model=CartRead)
async def clear_cart(
    current_user: User = Depends(get_current_user),
    service: CartService = Depends(get_cart_service),
) -> CartRead:
    # Remove all items from the authenticated user's cart.
    return await service.clear_cart(current_user.id)