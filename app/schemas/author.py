from datetime import datetime

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
    id: int
    name: str


class AuthorRead(AuthorBase):
    id: int
    created_at: datetime
