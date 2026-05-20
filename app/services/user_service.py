"""User service that encapsulates authentication and profile logic."""

from uuid import UUID

from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        # Store the repository used for user persistence and lookups.
        self._repo = repo

    async def register(self, data: UserCreate) -> User:
        # Register a new user after enforcing unique email and hashing password.
        existing = await self._repo.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered.",
            )

        payload = data.model_dump()
        password = payload.pop("password")
        payload["hashed_password"] = hash_password(password)
        return await self._repo.create(payload)

    async def authenticate(self, email: str, password: str) -> User:
        # Validate credentials and enforce active status.
        user = await self._repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive.",
            )

        return user

    async def get_profile(self, user_id: UUID) -> User:
        # Return a user profile or raise when missing.
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return user

    async def update_profile(self, user_id: UUID, data: UserUpdate) -> User:
        # Apply profile updates when provided, otherwise return current data.
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return user

        return await self._repo.update(user, update_data)
