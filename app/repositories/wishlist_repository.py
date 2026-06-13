"""Wishlist repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.wishlist import Wishlist, WishlistItem
from app.models.book import Book # Ensure you import your Book model

class WishlistRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    def _base_select(self):
        # We use selectinload to get items, and joinedload to fetch 
        # the specific 'book' relation for each item in one go.
        return select(Wishlist).options(
            selectinload(Wishlist.items).joinedload(WishlistItem.book)
        )

    async def get_by_user_id(self, user_id: UUID) -> Wishlist | None:
        # Retrieve a wishlist by user id with fully loaded items and books.
        result = await self._db.execute(self._base_select().where(Wishlist.user_id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user_id: UUID) -> Wishlist:
        # Persist a new wishlist for the given user.
        wishlist = Wishlist(user_id=user_id)
        self._db.add(wishlist)
        await self._db.flush()
        await self._db.refresh(wishlist)
        return wishlist

    async def get_item_by_id(self, wishlist_id: UUID, item_id: UUID) -> WishlistItem | None:
        # Retrieve a wishlist item by id within the given wishlist.
        # Note: If you need the book here too, add .options(joinedload(WishlistItem.book))
        result = await self._db.execute(
            select(WishlistItem)
            .options(joinedload(WishlistItem.book))
            .where(
                WishlistItem.wishlist_id == wishlist_id,
                WishlistItem.id == item_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_item_by_book(self, wishlist_id: UUID, book_id: UUID) -> WishlistItem | None:
        # Retrieve a wishlist item for the given book within the given wishlist.
        result = await self._db.execute(
            select(WishlistItem)
            .options(joinedload(WishlistItem.book))
            .where(
                WishlistItem.wishlist_id == wishlist_id,
                WishlistItem.book_id == book_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_item(self, wishlist: Wishlist, book_id: UUID) -> WishlistItem:
        # Persist a new wishlist item.
        item = WishlistItem(wishlist_id=wishlist.id, book_id=book_id)
        self._db.add(item)
        await self._db.flush()
        await self._db.refresh(item)
        return item

    async def delete_item(self, item: WishlistItem) -> None:
        # Remove a wishlist item from persistence.
        await self._db.delete(item)
        await self._db.flush()

    async def clear_items(self, wishlist: Wishlist) -> None:
        # Remove all items from the wishlist.
        result = await self._db.execute(
            select(WishlistItem).where(WishlistItem.wishlist_id == wishlist.id)
        )
        for item in result.scalars().all():
            await self._db.delete(item)
        await self._db.flush()