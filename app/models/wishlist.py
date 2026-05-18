import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .book import Book
    from .user import User


class Wishlist(BaseModel):
    __tablename__ = "wishlists"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="wishlist")
    items: Mapped[list["WishlistItem"]] = relationship(
        "WishlistItem",
        back_populates="wishlist",
        cascade="all, delete-orphan",
    )


class WishlistItem(BaseModel):
    __tablename__ = "wishlist_items"
    # Enforce one entry per (wishlist, book) pair.
    __table_args__ = (
        UniqueConstraint("wishlist_id", "book_id", name="uq_wishlist_items_wishlist_id_book_id"),
    )

    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wishlists.id"),
        nullable=False,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("books.id"),
        nullable=False,
    )

    wishlist: Mapped["Wishlist"] = relationship("Wishlist", back_populates="items")
    book: Mapped["Book"] = relationship("Book", back_populates="wishlist_items")
