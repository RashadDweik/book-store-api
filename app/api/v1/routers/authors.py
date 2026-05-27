"""Author catalog routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.repositories.author_repository import AuthorRepository
from app.schemas.author import AuthorCreate, AuthorRead, AuthorUpdate
from app.services.author_service import AuthorService


# Group author catalog endpoints under the /authors prefix.
router = APIRouter(prefix="/authors", tags=["Authors"])


def get_author_service(db: AsyncSession = Depends(get_db)) -> AuthorService:
    # Build a service with the request-scoped database session.
    return AuthorService(AuthorRepository(db))


@router.get("", response_model=list[AuthorRead])
async def list_authors(
    q: str | None = Query(None, min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AuthorService = Depends(get_author_service),
) -> list[AuthorRead]:
    # Return a filtered list of authors.
    return await service.list_authors(query=q, limit=limit, offset=offset)


@router.get("/{author_id}", response_model=AuthorRead)
async def read_author(
    author_id: UUID,
    service: AuthorService = Depends(get_author_service),
) -> AuthorRead:
    # Return details for a single author.
    return await service.get_author(author_id)


@router.post(
    "",
    response_model=AuthorRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_author(
    data: AuthorCreate,
    service: AuthorService = Depends(get_author_service),
) -> AuthorRead:
    # Create a new author entry.
    return await service.create_author(data)


@router.patch(
    "/{author_id}",
    response_model=AuthorRead,
    dependencies=[Depends(require_admin)],
)
async def update_author(
    author_id: UUID,
    data: AuthorUpdate,
    service: AuthorService = Depends(get_author_service),
) -> AuthorRead:
    # Update an author entry.
    return await service.update_author(author_id, data)


@router.delete(
    "/{author_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_author(
    author_id: UUID,
    service: AuthorService = Depends(get_author_service),
) -> None:
    # Delete an author entry.
    await service.delete_author(author_id)
    return None
