from datetime import datetime
from uuid import UUID

from .base import SchemaBase
from .role import RoleRead


class UserBase(SchemaBase):
    email: str
    is_active: bool = True
    role_id: UUID


class UserCreate(UserBase):
    password: str


class UserUpdate(SchemaBase):
    email: str | None = None
    is_active: bool | None = None
    role_id: UUID | None = None
    password: str | None = None


class UserRead(SchemaBase):
    id: UUID
    email: str
    is_active: bool
    role: RoleRead
    created_at: datetime
