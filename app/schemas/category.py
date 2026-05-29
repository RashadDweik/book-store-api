"""Pydantic schemas for book categories."""

from datetime import datetime
from uuid import UUID

from .base import SchemaBase


class CategoryBase(SchemaBase):
    name: str


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(SchemaBase):
    name: str | None = None


class CategorySummary(SchemaBase):
    id: UUID
    name: str


class CategoryRead(CategoryBase):
    id: UUID
    created_at: datetime