"""Role repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role


class RoleRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        """
        Initialize the repository with an asynchronous database session.
        
        Parameters:
            db (AsyncSession): Async SQLAlchemy session used for queries and persistence.
        """
        self._db = db

    async def get_id_by_name(self, name: str) -> UUID | None:
        # Retrieve a role id by its unique name.
        """
        Finds the UUID of the role with the given name.
        
        Performs a database lookup for a role whose name exactly matches the provided value and returns its id.
        
        Parameters:
            name (str): Role name to look up; expected to be the unique role identifier in the database.
        
        Returns:
            UUID | None: The role's `id` if a matching role exists, `None` otherwise.
        """
        result = await self._db.execute(select(Role.id).where(Role.name == name))
        return result.scalar_one_or_none()
