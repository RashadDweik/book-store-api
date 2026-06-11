"""User service that encapsulates authentication and profile logic."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, repo: UserRepository, roles: RoleRepository) -> None:
        # Store repositories used for persistence and lookups.
        self._repo = repo
        self._roles = roles

    @property
    def db(self):
        return getattr(self._repo, "_db", None)

    @staticmethod
    def _is_email_unique_violation(error: IntegrityError) -> bool:
        """Return True when IntegrityError is due to users.email uniqueness."""
        constraint_name = getattr(getattr(error, "orig", None), "constraint_name", None)
        if constraint_name == "uq_users_email":
            return True

        diag = getattr(getattr(error, "orig", None), "diag", None)
        if diag is not None and getattr(diag, "constraint_name", None) == "uq_users_email":
            return True

        message = str(getattr(error, "orig", error)).lower()
        if "uq_users_email" in message:
            return True
        if "users.email" in message and "unique" in message:
            return True
        if "key (email)" in message and "already exists" in message:
            return True
        return False

    async def register(self, data: UserCreate) -> User:
        # Register a new user after enforcing unique email and hashing password.
        existing = await self._repo.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered.",
            )

        user_role_id = await self._roles.get_id_by_name("user")
        if user_role_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default role 'user' is not configured.",
            )

        payload = data.model_dump()
        password = payload.pop("password")
        payload["hashed_password"] = hash_password(password)
        # Force all self-registrations to use the default 'user' role.
        payload["role_id"] = user_role_id
        try:
            created = await self._repo.create(payload)
        except IntegrityError as exc:
            if self._is_email_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered.",
                ) from exc
            raise
        reloaded = await self._repo.get_by_id(created.id)
        return reloaded or created

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

        try:
            updated = await self._repo.update(user, update_data)
        except IntegrityError as exc:
            if self._is_email_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered.",
                ) from exc
            raise
        reloaded = await self._repo.get_by_id(updated.id)
        return reloaded or updated

