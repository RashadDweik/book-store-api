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
    """
    Constructs a UserService using the provided asynchronous database session.
    
    Parameters:
        db (AsyncSession): Request-scoped async database session supplied by the dependency.
    
    Returns:
        UserService: A service configured with UserRepository and RoleRepository that use the given session.
    """
    return UserService(UserRepository(db), RoleRepository(db))


def get_refresh_token_store(request: Request) -> RefreshTokenStore:
    # Resolve the refresh token store from app state or build one lazily.
    # This keeps a single Redis connection per app instance.
    """
    Retrieve or lazily initialize the application's RefreshTokenStore.
    
    If a RefreshTokenStore is already attached to request.app.state it is returned; otherwise a new store is created via build_refresh_token_store(settings), stored on request.app.state, and returned for reuse across the application.
    
    Returns:
        RefreshTokenStore: The application's Redis-backed refresh token store.
    """
    store = getattr(request.app.state, "refresh_token_store", None)
    if store is None:
        store = build_refresh_token_store(settings)
        request.app.state.refresh_token_store = store
    return store


def get_auth_audit_log_service() -> AuthAuditLogService:
    """
    Constructs a new AuthAuditLogService instance for recording authentication audit events.
    
    Returns:
        AuthAuditLogService: An instance used to record authentication-related audit events.
    """
    return AuthAuditLogService()


def _get_request_ip(request: Request) -> str | None:
    """
    Extract the client's IP address from a Request.
    
    Returns:
        str: The client's IP address if available, `None` otherwise.
    """
    client = getattr(request, "client", None)
    if client is None:
        return None
    return getattr(client, "host", None)


def _get_user_agent(request: Request) -> str | None:
    """
    Retrieve the request's User-Agent header.
    
    Returns:
        str: The value of the `User-Agent` header, or `None` if the header is not present.
    """
    return request.headers.get("user-agent")


def _hash_refresh_token(refresh_token: str) -> str:
    """
    Compute a SHA-256 hash of a refresh token.
    
    Parameters:
        refresh_token (str): The raw refresh token to hash.
    
    Returns:
        str: Hexadecimal SHA-256 digest of the given refresh token.
    """
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
    """
    Create a new user account.
    
    Schedules an authentication audit event for the registration (recording IP and User-Agent) and returns the created user profile.
    
    Parameters:
        data (UserCreate): Payload with user registration details.
    
    Returns:
        UserResponse: The newly created user's profile.
    """
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
    """
    Authenticate the provided credentials and issue a new access token and refresh token.
    
    Authenticates the user using the supplied form credentials, persists the refresh token in the refresh token store, schedules an audit log entry, and returns both tokens. The request and background_tasks are used to record an audit event containing request metadata and a hash of the refresh token.
    
    Parameters:
        request (Request): Incoming HTTP request; used to extract IP address and User-Agent for audit logging.
        background_tasks (BackgroundTasks): Background task runner used to enqueue the audit log insertion.
        form_data (OAuth2PasswordRequestForm): Username and password credentials from the token request form.
    
    Returns:
        TokenResponse: An object containing `access_token` (short-lived JWT) and `refresh_token` (long-lived token).
    
    Raises:
        HTTPException: With status 503 if the refresh token store is unavailable.
    """
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
    """
    Validate a refresh token and issue a new access token while returning the original refresh token.
    
    Returns:
        TokenResponse: Contains a newly created access token and the provided refresh token.
    
    Raises:
        HTTPException: 401 Unauthorized if the refresh token is missing, has the wrong type, is invalid, or does not match the stored subject (includes 'WWW-Authenticate: Bearer' header).
        HTTPException: 503 Service Unavailable if the refresh token store cannot be accessed.
    """
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

    access_token = create_access_token(str(subject))
    return TokenResponse(access_token=access_token, refresh_token=payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: LogoutRequest,
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
    audit: AuthAuditLogService = Depends(get_auth_audit_log_service),
) -> None:
    # Validate refresh token and revoke it to end the session.
    """
    Revoke a refresh token to log out a user and schedule an audit event.
    
    Validates that the provided refresh token is well-formed and of type "refresh", revokes it in the refresh token store, and enqueues an audit event recording the logout (including a SHA-256 hash of the refresh token and request IP/user-agent). If the token's subject cannot be converted to a UUID, revocation still occurs but no audit event is recorded.
    
    Parameters:
        payload (LogoutRequest): Request body containing the `refresh_token` to revoke.
    
    Raises:
        HTTPException: 401 Unauthorized if the refresh token is missing required claims or is not a refresh token (includes `WWW-Authenticate: Bearer` header).
        HTTPException: 503 Service Unavailable if the refresh token store is unavailable.
    """
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
