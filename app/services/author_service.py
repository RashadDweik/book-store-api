"""Author service that encapsulates author domain logic."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.author import Author
from app.repositories.author_repository import AuthorRepository
from app.schemas.author import AuthorCreate, AuthorUpdate


class AuthorService:
    def __init__(self, repo: AuthorRepository) -> None:
        # Store repository used for persistence and lookups.
        self._repo = repo

    async def list_authors(
        self,
        *,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Author]:
        # Return a filtered list of authors.
        return await self._repo.list(query=query, limit=limit, offset=offset)

    async def get_author(self, author_id: UUID) -> Author:
        # Return an author or raise when missing.
        author = await self._repo.get_by_id(author_id)
        if author is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author not found.",
            )
        return author

    async def create_author(self, data: AuthorCreate) -> Author:
        # Create a new author.
        payload = data.model_dump()
        created = await self._repo.create(payload)
        reloaded = await self._repo.get_by_id(created.id)
        return reloaded or created

    async def update_author(self, author_id: UUID, data: AuthorUpdate) -> Author:
        # Update an author.
        author = await self._repo.get_by_id(author_id)
        if author is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author not found.",
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return author

        updated = await self._repo.update(author, update_data)
        reloaded = await self._repo.get_by_id(updated.id)
        return reloaded or updated

    async def delete_author(self, author_id: UUID) -> None:
        # Remove an author if it exists.
        author = await self._repo.get_by_id(author_id)
        if author is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author not found.",
            )
        await self._repo.delete(author)
