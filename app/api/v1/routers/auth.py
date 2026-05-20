"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.repositories.user_repository import UserRepository
from app.schemas.user import RefreshRequest, TokenResponse, UserCreate, UserResponse
from app.services.user_service import UserService


# Group authentication endpoints under the /auth prefix.
router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    # Build a service with the request-scoped database session.
    return UserService(UserRepository(db))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    # Register a new user and return the created profile.
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserService = Depends(get_user_service),
) -> TokenResponse:
    # Authenticate credentials and issue access/refresh tokens.
    user = await service.authenticate(form_data.username, form_data.password)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(payload: RefreshRequest) -> TokenResponse:
    # Validate refresh token and issue a new access token.
    token_payload = decode_token(payload.refresh_token)
    subject = token_payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(str(subject))
    return TokenResponse(access_token=access_token, refresh_token=payload.refresh_token)
