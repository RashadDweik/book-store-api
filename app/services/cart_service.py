"""Cart service that encapsulates cart domain logic."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.cart import Cart
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository
from app.schemas.cart import CartItemCreate, CartItemUpdate


class CartService:
    def __init__(self, repo: CartRepository, books: BookRepository) -> None:
        # Store repositories used for persistence and lookups.
        self._repo = repo
        self._books = books

    async def _get_or_create_cart(self, user_id: UUID) -> Cart:
        cart = await self._repo.get_by_user_id(user_id)
        if cart is None:
            cart = await self._repo.create(user_id)
        return cart

    async def _get_cart(self, user_id: UUID) -> Cart:
        cart = await self._repo.get_by_user_id(user_id)
        if cart is None:
            cart = await self._repo.create(user_id)
        return cart

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if quantity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity must be at least 1.",
            )

    async def get_cart(self, user_id: UUID) -> Cart:
        # Return the user's cart, creating it on first access.
        return await self._get_or_create_cart(user_id)

    async def add_item(self, user_id: UUID, data: CartItemCreate) -> Cart:
        # Add a book to the cart, merging quantities when the item already exists.
        self._validate_quantity(data.quantity)
        book = await self._books.get_by_id(data.book_id)
        if book is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found.",
            )
        cart = await self._get_or_create_cart(user_id)
        existing = await self._repo.get_item_by_book(cart.id, data.book_id)
        if existing is None:
            await self._repo.add_item(cart, data.book_id, data.quantity)
        else:
            await self._repo.update_item(existing, existing.quantity + data.quantity)
        return await self._get_or_create_cart(user_id)

    async def update_item(self, user_id: UUID, item_id: UUID, data: CartItemUpdate) -> Cart:
        # Update the quantity for a specific cart item.
        cart = await self._get_or_create_cart(user_id)
        item = await self._repo.get_item_by_id(cart.id, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found.",
            )

        update_data = data.model_dump(exclude_unset=True)
        quantity = update_data.get("quantity")
        if quantity is None:
            return await self._get_or_create_cart(user_id)

        self._validate_quantity(quantity)
        await self._repo.update_item(item, quantity)
        return await self._get_or_create_cart(user_id)

    async def remove_item(self, user_id: UUID, item_id: UUID) -> Cart:
        # Remove a single cart item.
        cart = await self._get_or_create_cart(user_id)
        item = await self._repo.get_item_by_id(cart.id, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found.",
            )

        await self._repo.delete_item(item)
        return await self._get_or_create_cart(user_id)

    async def clear_cart(self, user_id: UUID) -> Cart:
        # Remove all items from the user's cart.
        cart = await self._get_or_create_cart(user_id)
        await self._repo.clear_items(cart)
        return await self._get_or_create_cart(user_id)