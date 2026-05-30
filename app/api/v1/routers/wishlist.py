"""Wishlist routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.book_repository import BookRepository
from app.repositories.wishlist_repository import WishlistRepository
from app.schemas.wishlist import WishlistItemCreate, WishlistRead
from app.services.wishlist_service import WishlistService


# Group wishlist endpoints under the /wishlist prefix.
router = APIRouter(prefix="/wishlist", tags=["Wishlist"])


def get_wishlist_service(db: AsyncSession = Depends(get_db)) -> WishlistService:
    # Build a service with the request-scoped database session.
    return WishlistService(WishlistRepository(db), BookRepository(db))


@router.get("", response_model=WishlistRead)
async def read_wishlist(
    current_user: User = Depends(get_current_user),
    service: WishlistService = Depends(get_wishlist_service),
) -> WishlistRead:
    # Return the authenticated user's wishlist.
    return await service.get_wishlist(current_user.id)


@router.post("/items", response_model=WishlistRead, status_code=status.HTTP_201_CREATED)
async def add_wishlist_item(
    data: WishlistItemCreate,
    current_user: User = Depends(get_current_user),
    service: WishlistService = Depends(get_wishlist_service),
) -> WishlistRead:
    # Add a book to the authenticated user's wishlist.
    return await service.add_item(current_user.id, data)


@router.delete("/items/{item_id}", response_model=WishlistRead)
async def delete_wishlist_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WishlistService = Depends(get_wishlist_service),
) -> WishlistRead:
    # Remove a wishlist item from the authenticated user's wishlist.
    return await service.remove_item(current_user.id, item_id)


@router.delete("", response_model=WishlistRead)
async def clear_wishlist(
    current_user: User = Depends(get_current_user),
    service: WishlistService = Depends(get_wishlist_service),
) -> WishlistRead:
    # Remove all items from the authenticated user's wishlist.
    return await service.clear_wishlist(current_user.id)