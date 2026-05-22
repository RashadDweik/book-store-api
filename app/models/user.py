import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .cart import Cart
    from .order import Order
    from .role import Role
    from .wishlist import Wishlist


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
        index=True,
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    # uselist=False makes these one-to-one relationships.
    cart: Mapped["Cart"] = relationship(
        "Cart",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    wishlist: Mapped["Wishlist"] = relationship(
        "Wishlist",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
