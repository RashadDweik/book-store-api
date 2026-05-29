"""Category repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    async def get_by_id(self, category_id: UUID) -> Category | None:
        # Retrieve a category by UUID, returning None when missing.
        result = await self._db.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Category]:
        # List categories with optional name filtering and pagination.
        stmt = select(Category)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(Category.name.ilike(pattern))
        stmt = stmt.order_by(Category.name.asc()).limit(limit).offset(offset)
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def create(self, category_data: dict) -> Category:
        # Persist a new category and return the refreshed instance.
        category = Category(**category_data)
        self._db.add(category)
        await self._db.flush()
        await self._db.refresh(category)
        return category

    async def update(self, category: Category, update_data: dict) -> Category:
        # Apply updates to an existing category and refresh state.
        for key, value in update_data.items():
            setattr(category, key, value)
        self._db.add(category)
        await self._db.flush()
        await self._db.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        # Remove a category from persistence.
        await self._db.delete(category)
        await self._db.flush()