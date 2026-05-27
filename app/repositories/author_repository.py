"""Author repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author


class AuthorRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    async def get_by_id(self, author_id: UUID) -> Author | None:
        # Retrieve an author by UUID, returning None when missing.
        result = await self._db.execute(select(Author).where(Author.id == author_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Author]:
        # List authors with optional name filtering and pagination.
        stmt = select(Author)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(Author.name.ilike(pattern))
        stmt = stmt.order_by(Author.name.asc()).limit(limit).offset(offset)
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def create(self, author_data: dict) -> Author:
        # Persist a new author from a field dictionary and return the instance.
        author = Author(**author_data)
        self._db.add(author)
        await self._db.flush()
        await self._db.refresh(author)
        return author

    async def update(self, author: Author, update_data: dict) -> Author:
        # Apply field updates to an existing author and refresh state.
        for key, value in update_data.items():
            setattr(author, key, value)
        self._db.add(author)
        await self._db.flush()
        await self._db.refresh(author)
        return author

    async def delete(self, author: Author) -> None:
        # Remove an author from persistence.
        await self._db.delete(author)
        await self._db.flush()

    async def get_by_ids(self, author_ids: list[UUID]) -> list[Author]:
        # Return authors that match any of the provided ids.
        if not author_ids:
            return []
        result = await self._db.execute(select(Author).where(Author.id.in_(author_ids)))
        return result.scalars().all()
