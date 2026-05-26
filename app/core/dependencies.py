"""Authentication dependencies for FastAPI routes."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.role import Role
from app.models.user import User


# OAuth2 bearer token extractor for secured endpoints.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Resolve the current user from the JWT subject and enforce active status.
    """
    Resolve the authenticated User associated with a JWT bearer token.
    
    Decodes the provided OAuth2 bearer token, loads the corresponding User (including their role) from the database, and enforces that the user exists and is active.
    
    Returns:
        The resolved `User` instance corresponding to the token's `sub` claim.
    
    Raises:
        HTTPException: 401 if the token is invalid or expired.
        HTTPException: 401 if no user matches the token's subject.
        HTTPException: 403 if the resolved user exists but is not active.
    """
    payload = decode_token(token)
    subject = payload.get("sub")

    try:
        user_id = UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive.",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    # Alias dependency for readability in route signatures.
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Guard routes that require admin privileges.
    result = await db.execute(select(Role.name).where(Role.id == current_user.role_id))
    role_name = result.scalar_one_or_none()

    if role_name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )

    return current_user
