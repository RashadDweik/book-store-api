"""User profile routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService


# Group user profile endpoints under the /users prefix.
router = APIRouter(prefix="/users", tags=["Users"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    # Build a service with the request-scoped database session.
    """
    Provide a UserService instance wired to repositories using the request-scoped database session.
    
    Returns:
        UserService: Service constructed with UserRepository and RoleRepository bound to the provided `db`.
    """
    return UserService(UserRepository(db), RoleRepository(db))


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    # Return the authenticated user's profile.
    """
    Return the authenticated user's profile.
    
    Returns:
        UserResponse: The authenticated user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    # Apply updates to the authenticated user's profile.
    """
    Update the authenticated user's profile with the provided changes.
    
    Parameters:
        data (UserUpdate): Fields to update on the current user's profile.
    
    Returns:
        UserResponse: The updated user profile.
    """
    return await service.update_profile(current_user.id, data)
