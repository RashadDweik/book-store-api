"""Redis-backed cache for live book stock values."""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import Settings


@dataclass
class InventoryCache:
    redis: Redis
    key_prefix: str = "inventory:book-stock"

    def _key(self, book_id) -> str:
        return f"{self.key_prefix}:{book_id}"

    async def get_stock(self, book_id) -> int | None:
        value = await self.redis.get(self._key(book_id))
        if value is None:
            return None
        return int(value)

    async def set_stock(self, book_id, stock: int) -> None:
        await self.redis.set(self._key(book_id), int(stock))

    async def delete_stock(self, book_id) -> None:
        await self.redis.delete(self._key(book_id))

    async def hydrate_book(self, book) -> None:
        cached_stock = await self.get_stock(book.id)
        if cached_stock is not None:
            book.stock = cached_stock

    async def hydrate_books(self, books: list) -> None:
        for book in books:
            await self.hydrate_book(book)

    async def close(self) -> None:
        await self.redis.aclose()


def build_inventory_cache(settings: Settings) -> InventoryCache:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return InventoryCache(redis=redis)