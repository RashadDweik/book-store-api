"""Cart repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem


class CartRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    def _base_select(self):
        return select(Cart).options(selectinload(Cart.items))

    async def get_by_user_id(self, user_id: UUID) -> Cart | None:
        # Retrieve a cart by user id, returning None when missing.
        result = await self._db.execute(self._base_select().where(Cart.user_id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user_id: UUID) -> Cart:
        # Persist a new cart for the given user.
        cart = Cart(user_id=user_id)
        self._db.add(cart)
        await self._db.flush()
        await self._db.refresh(cart)
        return cart

    async def get_item_by_id(self, cart_id: UUID, item_id: UUID) -> CartItem | None:
        # Retrieve a cart item by id within the given cart.
        result = await self._db.execute(
            select(CartItem).where(CartItem.cart_id == cart_id, CartItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_item_by_book(self, cart_id: UUID, book_id: UUID) -> CartItem | None:
        # Retrieve a cart item for the given book within the given cart.
        result = await self._db.execute(
            select(CartItem).where(CartItem.cart_id == cart_id, CartItem.book_id == book_id)
        )
        return result.scalar_one_or_none()

    async def add_item(self, cart: Cart, book_id: UUID, quantity: int) -> CartItem:
        # Persist a new cart item.
        item = CartItem(cart_id=cart.id, book_id=book_id, quantity=quantity)
        self._db.add(item)
        await self._db.flush()
        await self._db.refresh(item)
        return item

    async def update_item(self, item: CartItem, quantity: int) -> CartItem:
        # Update a cart item's quantity.
        item.quantity = quantity
        self._db.add(item)
        await self._db.flush()
        await self._db.refresh(item)
        return item

    async def delete_item(self, item: CartItem) -> None:
        # Remove a cart item from persistence.
        await self._db.delete(item)
        await self._db.flush()

    async def clear_items(self, cart: Cart) -> None:
        # Remove all items from the cart.
        result = await self._db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
        for item in result.scalars().all():
            await self._db.delete(item)
        await self._db.flush()

    async def get_cart_dict(self, user_id: UUID) -> dict:
        """Return a plain mapping for the cart and its items for safe serialization."""
        cart = await self.get_by_user_id(user_id)
        if cart is None:
            cart = await self.create(user_id)

        items_result = await self._db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
        items = []
        for item in items_result.scalars().all():
            items.append(
                {
                    "id": item.id,
                    "book_id": item.book_id,
                    "quantity": item.quantity,
                    "created_at": item.created_at,
                }
            )

        return {
            "id": cart.id,
            "user_id": cart.user_id,
            "created_at": cart.created_at,
            "items": items,
        }