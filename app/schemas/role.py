from datetime import datetime
from uuid import UUID

from .base import SchemaBase


class RoleRead(SchemaBase):
    id: UUID
    name: str
    created_at: datetime
