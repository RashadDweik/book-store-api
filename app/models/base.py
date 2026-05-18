"""Declarative base and shared mixins for SQLAlchemy models."""

from datetime import datetime
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
	"""Base class that provides metadata for all models."""


class TimestampMixin:
	"""Shared UUID primary key and audit timestamps."""

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		primary_key=True,
		default=uuid.uuid4,
	)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		nullable=False,
	)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		server_default=func.now(),
		onupdate=func.now(),
		nullable=False,
	)


class BaseModel(Base, TimestampMixin):
	"""Abstract base model that includes UUID and timestamps."""

	__abstract__ = True
