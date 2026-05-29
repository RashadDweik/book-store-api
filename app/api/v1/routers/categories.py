"""Category catalog routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.category_service import CategoryService


router = APIRouter(prefix="/categories", tags=["Categories"])


def get_category_service(db: AsyncSession = Depends(get_db)) -> CategoryService:
    # Build a service with the request-scoped database session.
    return CategoryService(CategoryRepository(db))


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    q: str | None = Query(None, min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryRead]:
    # Return a filtered list of categories.
    return await service.list_categories(query=q, limit=limit, offset=offset)


@router.get("/{category_id}", response_model=CategoryRead)
async def read_category(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service),
) -> CategoryRead:
    # Return details for a single category.
    return await service.get_category(category_id)


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_category(
    data: CategoryCreate,
    service: CategoryService = Depends(get_category_service),
) -> CategoryRead:
    # Create a new category entry.
    return await service.create_category(data)


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    dependencies=[Depends(require_admin)],
)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    service: CategoryService = Depends(get_category_service),
) -> CategoryRead:
    # Update a category entry.
    return await service.update_category(category_id, data)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_category(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service),
) -> None:
    # Delete a category entry.
    await service.delete_category(category_id)
    return None