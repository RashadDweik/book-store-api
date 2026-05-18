from datetime import datetime
from uuid import UUID

from .base import SchemaBase


class AuthorBase(SchemaBase):
    name: str
    bio: str | None = None


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(SchemaBase):
    name: str | None = None
    bio: str | None = None


class AuthorSummary(SchemaBase):
    id: UUID
    name: str


class AuthorRead(AuthorBase):
    id: UUID
    created_at: datetime
