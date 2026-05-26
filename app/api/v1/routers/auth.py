"""Authentication routes."""

from datetime import timedelta
import hashlib
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.refresh_token_store import RefreshTokenStore, build_refresh_token_store
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import LogoutRequest, RefreshRequest, TokenResponse, UserCreate, UserResponse
from app.services.auth_audit_log_service import AuthAuditLogService
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


def get_auth_audit_log_service() -> AuthAuditLogService:
    return AuthAuditLogService()


def _get_request_ip(request: Request) -> str | None:
    client = getattr(request, "client", None)
    if client is None:
        return None
    return getattr(client, "host", None)


def _get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    background_tasks: BackgroundTasks,
    data: UserCreate,
    service: UserService = Depends(get_user_service),
    audit: AuthAuditLogService = Depends(get_auth_audit_log_service),
) -> UserResponse:
    # Register a new user and return the created profile.
    user = await service.register(data)
    background_tasks.add_task(
        audit.insert_event,
        user_id=UUID(str(user.id)),
        event="register",
        ip_address=_get_request_ip(request),
        user_agent=_get_user_agent(request),
        refresh_token_hash=None,
    )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_user(
    request: Request,
    background_tasks: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserService = Depends(get_user_service),
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
    audit: AuthAuditLogService = Depends(get_auth_audit_log_service),
) -> TokenResponse:
    # Authenticate credentials and issue access/refresh tokens.
    user = await service.authenticate(form_data.username, form_data.password)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    # Persist refresh token so we can reject revoked/unknown tokens later.
    try:
        await refresh_store.store(
            refresh_token,
            str(user.id),
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh token store is unavailable. Try again later.",
        ) from exc

    background_tasks.add_task(
        audit.insert_event,
        user_id=UUID(str(user.id)),
        event="login",
        ip_address=_get_request_ip(request),
        user_agent=_get_user_agent(request),
        refresh_token_hash=_hash_refresh_token(refresh_token),
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
    try:
        stored_subject = await refresh_store.get_subject(payload.refresh_token)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh token store is unavailable. Try again later.",
        ) from exc
    if stored_subject is None or stored_subject != str(subject):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_refresh_token = create_refresh_token(str(subject))
    try:
        await refresh_store.store(
            new_refresh_token,
            str(subject),
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh token store is unavailable. Try again later.",
        ) from exc

    try:
        await refresh_store.revoke(payload.refresh_token)
    except RedisError as exc:
        try:
            await refresh_store.revoke(new_refresh_token)
        except RedisError:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh token store is unavailable. Try again later.",
        ) from exc

    access_token = create_access_token(str(subject))
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: LogoutRequest,
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
    audit: AuthAuditLogService = Depends(get_auth_audit_log_service),
) -> None:
    # Validate refresh token and revoke it to end the session.
    token_payload = decode_token(payload.refresh_token)
    subject = token_payload.get("sub")
    if not subject or token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        await refresh_store.revoke(payload.refresh_token)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh token store is unavailable. Try again later.",
        ) from exc

    try:
        user_id = UUID(str(subject))
    except (TypeError, ValueError):
        return None

    background_tasks.add_task(
        audit.insert_event,
        user_id=user_id,
        event="logout",
        ip_address=_get_request_ip(request),
        user_agent=_get_user_agent(request),
        refresh_token_hash=_hash_refresh_token(payload.refresh_token),
    )

    return None
