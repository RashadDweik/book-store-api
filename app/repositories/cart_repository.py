from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from uuid import UUID

from app.models.cart import Cart, CartItem
from app.models.book import Book


class CartRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _base_select(self):
        return select(Cart).options(
            selectinload(Cart.items).options(
                joinedload(CartItem.book).options(
                    selectinload(Book.authors),
                    joinedload(Book.category),
                )
            )
        )

    async def get_by_user_id(self, user_id: UUID) -> Cart | None:
        result = await self._db.execute(
            self._base_select().where(Cart.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: UUID) -> Cart:
        cart = Cart(user_id=user_id)
        self._db.add(cart)
        await self._db.flush()
        result = await self._db.execute(
            self._base_select().where(Cart.user_id == user_id)
        )
        return result.scalar_one()

    async def get_item_by_id(self, cart_id: UUID, item_id: UUID) -> CartItem | None:
        result = await self._db.execute(
            select(CartItem)
            .options(
                joinedload(CartItem.book).options(
                    selectinload(Book.authors),
                    joinedload(Book.category),
                )
            )
            .where(CartItem.cart_id == cart_id, CartItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_item_by_book(self, cart_id: UUID, book_id: UUID) -> CartItem | None:
        result = await self._db.execute(
            select(CartItem)
            .options(
                joinedload(CartItem.book).options(
                    selectinload(Book.authors),
                    joinedload(Book.category),
                )
            )
            .where(CartItem.cart_id == cart_id, CartItem.book_id == book_id)
        )
        return result.scalar_one_or_none()

    async def add_item(self, cart: Cart, book_id: UUID, quantity: int) -> CartItem:
        item = CartItem(cart_id=cart.id, book_id=book_id, quantity=quantity)
        self._db.add(item)
        await self._db.flush()
        await self._db.refresh(item)
        return item

    async def update_item(self, item: CartItem, quantity: int) -> CartItem:
        item.quantity = quantity
        await self._db.flush()
        await self._db.refresh(item)
        return item

    async def delete_item(self, item: CartItem) -> None:
        await self._db.delete(item)
        await self._db.flush()

    async def clear_items(self, cart: Cart) -> None:
        result = await self._db.execute(
            select(CartItem).where(CartItem.cart_id == cart.id)
        )
        for item in result.scalars().all():
            await self._db.delete(item)
        await self._db.flush()