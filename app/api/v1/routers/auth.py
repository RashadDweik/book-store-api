"""Authentication routes."""

from datetime import timedelta
import hashlib
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
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
from app.schemas.user import TokenResponse, UserCreate, UserResponse
from app.services.auth_audit_log_service import AuthAuditLogService
from app.services.user_service import UserService


# Group authentication endpoints under the /auth prefix.
router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _refresh_cookie_options() -> dict[str, str | bool | int | None]:
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    # Keep the refresh token in an HttpOnly cookie so the browser stores it,
    # but frontend JavaScript cannot read or overwrite it.
    return {
        "key": settings.REFRESH_COOKIE_NAME,
        "httponly": True,
        "secure": settings.REFRESH_COOKIE_SECURE,
        "samesite": settings.REFRESH_COOKIE_SAMESITE,
        "max_age": max_age,
        "path": settings.REFRESH_COOKIE_PATH,
        "domain": settings.REFRESH_COOKIE_DOMAIN,
    }


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    options = _refresh_cookie_options()
    response.set_cookie(
        key=str(options["key"]),
        value=refresh_token,
        httponly=bool(options["httponly"]),
        secure=bool(options["secure"]),
        samesite=str(options["samesite"]),
        max_age=int(options["max_age"]),
        path=str(options["path"]),
        domain=options["domain"],
    )


def _delete_refresh_cookie(response: Response) -> None:
    options = _refresh_cookie_options()
    response.delete_cookie(
        key=str(options["key"]),
        path=str(options["path"]),
        domain=options["domain"],
    )


def _resolve_refresh_token(request: Request) -> str:
    # Cookie-only auth keeps the browser as the token holder and avoids exposing
    # refresh tokens to frontend JavaScript.
    cookie_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token is invalid or expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )


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
@limiter.limit("3/minute")
async def register_user(
    request: Request,
    background_tasks: BackgroundTasks,
    data: UserCreate,
    service: UserService = Depends(get_user_service),
    audit: AuthAuditLogService = Depends(get_auth_audit_log_service),
) -> UserResponse:
    # Register a new user and return the created profile.
    user = await service.register(data)
    db = getattr(service, "db", None)
    if isinstance(db, AsyncSession):
        await audit.insert_event_in_session(
            db,
            user_id=UUID(str(user.id)),
            event="register",
            ip_address=_get_request_ip(request),
            user_agent=_get_user_agent(request),
            refresh_token_hash=None,
        )
    else:
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
    response: Response,
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
    # Return the access token in JSON for the frontend, but store the refresh
    # token in a cookie so browser sessions can survive reloads and restarts.
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
) -> TokenResponse:
    # Validate refresh token and issue a new access token.
    refresh_token = _resolve_refresh_token(request)
    token_payload = decode_token(refresh_token)
    subject = token_payload.get("sub")
    if not subject or token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure the refresh token exists in storage and matches the subject.
    try:
        stored_subject = await refresh_store.get_subject(refresh_token)
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
        await refresh_store.revoke(refresh_token)
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
    # Rotate the cookie whenever we rotate the refresh token to keep browser and
    # server-side state aligned.
    _set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
    audit: AuthAuditLogService = Depends(get_auth_audit_log_service),
) -> None:
    # Validate refresh token and revoke it to end the session.
    refresh_token = _resolve_refresh_token(request)
    token_payload = decode_token(refresh_token)
    subject = token_payload.get("sub")
    if not subject or token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        await refresh_store.revoke(refresh_token)
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
        refresh_token_hash=_hash_refresh_token(refresh_token),
    )

    # Clear the browser cookie so a logged-out tab cannot keep reusing the old
    # refresh token after the server-side revocation completes.
    _delete_refresh_cookie(response)
    return None
