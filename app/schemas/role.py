from datetime import datetime

from .base import SchemaBase


class RoleRead(SchemaBase):
    id: int
    name: str
    created_at: datetime
