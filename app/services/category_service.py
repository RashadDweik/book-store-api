"""Category service that encapsulates category domain logic."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    def __init__(self, repo: CategoryRepository) -> None:
        # Store the repository used for persistence and lookups.
        self._repo = repo

    async def list_categories(
        self,
        *,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Category]:
        # Return a filtered list of categories.
        return await self._repo.list(query=query, limit=limit, offset=offset)

    async def get_category(self, category_id: UUID) -> Category:
        # Return a category or raise when missing.
        category = await self._repo.get_by_id(category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        return category

    async def create_category(self, data: CategoryCreate) -> Category:
        # Create a category and reload it so response fields are complete.
        category = await self._repo.create(data.model_dump())
        reloaded = await self._repo.get_by_id(category.id)
        return reloaded or category

    async def update_category(self, category_id: UUID, data: CategoryUpdate) -> Category:
        # Update a category if any fields were supplied.
        category = await self._repo.get_by_id(category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return category

        updated = await self._repo.update(category, update_data)
        reloaded = await self._repo.get_by_id(updated.id)
        return reloaded or updated

    async def delete_category(self, category_id: UUID) -> None:
        # Remove a category if it exists.
        category = await self._repo.get_by_id(category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        await self._repo.delete(category)