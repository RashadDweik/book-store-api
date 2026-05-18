from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from .author import book_authors
from .base import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)
    isbn = Column(String(32), nullable=True, unique=True, index=True)
    stock = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Authors is many-to-many; dependent items are deleted with the book.
    authors = relationship("Author", secondary=book_authors, back_populates="books")
    cart_items = relationship("CartItem", back_populates="book", cascade="all, delete-orphan")
    wishlist_items = relationship("WishlistItem", back_populates="book", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="book")
