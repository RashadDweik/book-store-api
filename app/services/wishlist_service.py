"""Wishlist service that encapsulates wishlist domain logic."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.book import Book
from app.models.wishlist import Wishlist
from app.repositories.book_repository import BookRepository
from app.repositories.wishlist_repository import WishlistRepository
from app.schemas.wishlist import WishlistItemCreate


class WishlistService:
    def __init__(self, repo: WishlistRepository, books: BookRepository) -> None:
        # Store repositories used for persistence and lookups.
        self._repo = repo
        self._books = books

    async def _get_or_create_wishlist(self, user_id: UUID) -> Wishlist:
        wishlist = await self._repo.get_by_user_id(user_id)
        if wishlist is None:
            wishlist = await self._repo.create(user_id)
        return wishlist

    async def _ensure_book_exists(self, book_id: UUID) -> Book:
        book = await self._books.get_by_id(book_id)
        if book is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )
        return book

    async def get_wishlist(self, user_id: UUID) -> Wishlist:
        # Return the user's wishlist, creating it on first access.
        return await self._get_or_create_wishlist(user_id)

    async def add_item(self, user_id: UUID, data: WishlistItemCreate) -> Wishlist:
        # Add a book to the wishlist and keep operation idempotent for duplicates.
        await self._ensure_book_exists(data.book_id)
        wishlist = await self._get_or_create_wishlist(user_id)
        existing = await self._repo.get_item_by_book(wishlist.id, data.book_id)
        if existing is None:
            await self._repo.add_item(wishlist, data.book_id)
        return await self._get_or_create_wishlist(user_id)

    async def remove_item(self, user_id: UUID, item_id: UUID) -> Wishlist:
        # Remove a single wishlist item.
        wishlist = await self._get_or_create_wishlist(user_id)
        item = await self._repo.get_item_by_id(wishlist.id, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wishlist item not found.",
            )

        await self._repo.delete_item(item)
        return await self._get_or_create_wishlist(user_id)

    async def clear_wishlist(self, user_id: UUID) -> Wishlist:
        # Remove all items from the user's wishlist.
        wishlist = await self._get_or_create_wishlist(user_id)
        await self._repo.clear_items(wishlist)
        return await self._get_or_create_wishlist(user_id)