from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .author import book_authors
from .base import BaseModel

if TYPE_CHECKING:
    from .author import Author
    from .cart import CartItem
    from .order import OrderItem
    from .wishlist import WishlistItem


class Book(BaseModel):
    __tablename__ = "books"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    release_date: Mapped[date | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Authors is many-to-many; dependent items are deleted with the book.
    authors: Mapped[list["Author"]] = relationship(
        "Author",
        secondary=book_authors,
        back_populates="books",
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="book",
        cascade="all, delete-orphan",
    )
    wishlist_items: Mapped[list["WishlistItem"]] = relationship(
        "WishlistItem",
        back_populates="book",
        cascade="all, delete-orphan",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="book",
    )
