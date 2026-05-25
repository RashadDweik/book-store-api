"""Authentication routes."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.refresh_token_store import RefreshTokenStore, build_refresh_token_store
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import RefreshRequest, TokenResponse, UserCreate, UserResponse
from app.services.user_service import UserService


# Group authentication endpoints under the /auth prefix.
router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    # Build a service with the request-scoped database session.
    return UserService(UserRepository(db), RoleRepository(db))


def get_refresh_token_store(request: Request) -> RefreshTokenStore:
    # Resolve the refresh token store from app state or build one lazily.
    # This keeps a single Redis connection per app instance.
    store = getattr(request.app.state, "refresh_token_store", None)
    if store is None:
        store = build_refresh_token_store(settings)
        request.app.state.refresh_token_store = store
    return store


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
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
) -> TokenResponse:
    # Authenticate credentials and issue access/refresh tokens.
    user = await service.authenticate(form_data.username, form_data.password)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    # Persist refresh token so we can reject revoked/unknown tokens later.
    await refresh_store.store(
        refresh_token,
        str(user.id),
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    payload: RefreshRequest,
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
) -> TokenResponse:
    # Validate refresh token and issue a new access token.
    token_payload = decode_token(payload.refresh_token)
    subject = token_payload.get("sub")
    if not subject or token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure the refresh token exists in storage and matches the subject.
    stored_subject = await refresh_store.get_subject(payload.refresh_token)
    if stored_subject is None or stored_subject != str(subject):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(str(subject))
    return TokenResponse(access_token=access_token, refresh_token=payload.refresh_token)
