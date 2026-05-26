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
        """
        Initialize the service with repository instances for user persistence and role lookups.
        """
        self._repo = repo
        self._roles = roles

    @staticmethod
    def _is_email_unique_violation(error: IntegrityError) -> bool:
        """
        Detect whether an IntegrityError corresponds to a unique constraint violation for the users.email column.
        
        Parameters:
            error (IntegrityError): The database integrity error to inspect.
        
        Returns:
            True if the error indicates a unique constraint violation for `users.email`, False otherwise.
        """
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
        """
        Register a new user, enforcing email uniqueness, assigning the default "user" role, and hashing the provided password.
        
        Parameters:
            data (UserCreate): User creation payload containing user fields including a plaintext `password`.
        
        Returns:
            User: The created user record; the repository is queried for a fresh copy and that reloaded instance is returned when available.
        
        Raises:
            HTTPException: With status 400 and detail "Email already registered." if the email is already in use.
            HTTPException: With status 500 and detail "Default role 'user' is not configured." if the default role cannot be resolved.
            IntegrityError: Re-raised for integrity violations that are not recognized as the users.email unique constraint.
        """
        existing = await self._repo.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
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
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered.",
                ) from exc
            raise
        reloaded = await self._repo.get_by_id(created.id)
        return reloaded or created

    async def authenticate(self, email: str, password: str) -> User:
        # Validate credentials and enforce active status.
        """
        Authenticate a user by email and password and enforce that the account is active.
        
        Returns:
            The authenticated User object.
        
        Raises:
            HTTPException: status 401 when the email or password are invalid.
            HTTPException: status 403 when the user's account is inactive.
        """
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
        """
        Retrieve the user profile for the given user identifier.
        
        Returns:
            user (User): The user matching `user_id`.
        
        Raises:
            HTTPException: If no user exists for the given `user_id` (404).
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return user

    async def update_profile(self, user_id: UUID, data: UserUpdate) -> User:
        # Apply profile updates when provided, otherwise return current data.
        """
        Update a user's profile with the fields provided in `data`.
        
        Parameters:
            user_id (UUID): Identifier of the user to update.
            data (UserUpdate): Partial user data; only fields explicitly set on this model will be applied.
        
        Returns:
            User: The updated user object; the repository is reloaded when possible and the reloaded user is returned.
        
        Raises:
            HTTPException: with 404 status if the user does not exist.
            HTTPException: with 400 status if the update violates the email-uniqueness constraint (email already registered).
        """
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
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered.",
                ) from exc
            raise
        reloaded = await self._repo.get_by_id(updated.id)
        return reloaded or updated

