"""Role repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role


class RoleRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    async def get_id_by_name(self, name: str) -> UUID | None:
        # Retrieve a role id by its unique name.
        result = await self._db.execute(select(Role.id).where(Role.name == name))
        return result.scalar_one_or_none()
