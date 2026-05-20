"""User repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        self._db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        # Retrieve a user by UUID, returning None when missing.
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        # Retrieve a user by email, returning None when missing.
        result = await self._db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        # Persist a new user from a field dictionary and return the instance.
        user = User(**user_data)
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user

    async def update(self, user: User, update_data: dict) -> User:
        # Apply field updates to an existing user and refresh state.
        for key, value in update_data.items():
            setattr(user, key, value)
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user
