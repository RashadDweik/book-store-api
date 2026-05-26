"""User repository for database access operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        # Store the async session used for queries and persistence.
        """
        Initialize the repository with an async SQLAlchemy session.
        
        Parameters:
            db (AsyncSession): Async SQLAlchemy session used for queries and persistence by repository methods.
        """
        self._db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        # Retrieve a user by UUID, returning None when missing.
        """
        Retrieve a User by its UUID.
        
        Returns:
            `User` instance when a user with the given id exists, `None` otherwise.
        """
        result = await self._db.execute(
            select(User).options(selectinload(User.role)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        # Retrieve a user by email, returning None when missing.
        """
        Fetches the User with the given email and eagerly loads its `role` relationship.
        
        The returned User instance will include the `role` relationship populated via eager loading.
        
        Returns:
            User | None: The matching User instance, or `None` if no user has the given email.
        """
        result = await self._db.execute(
            select(User).options(selectinload(User.role)).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        # Persist a new user from a field dictionary and return the instance.
        """
        Create and persist a User from a mapping of field values.
        
        Parameters:
            user_data (dict): Mapping of field names to values used to construct the User.
        
        Returns:
            User: The persisted User instance with database-populated fields (e.g., id, timestamps) refreshed.
        """
        user = User(**user_data)
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user

    async def update(self, user: User, update_data: dict) -> User:
        # Apply field updates to an existing user and refresh state.
        """
        Apply attribute updates from a mapping to an existing User and persist the changes to the database session.
        
        The provided mapping's keys are set as attributes on `user`; the instance is added to the session, flushed, and refreshed so the returned object reflects persisted state.
        
        Parameters:
            user (User): The existing user instance to update.
            update_data (dict): Mapping of attribute names to their new values.
        
        Returns:
            User: The updated user instance with refreshed state.
        """
        for key, value in update_data.items():
            setattr(user, key, value)
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user
