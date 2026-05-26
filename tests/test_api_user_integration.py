import os
from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from redis.exceptions import RedisError
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test-secret"

from app.api.v1.routers import auth as auth_router
from app.api.v1.routers import users as users_router
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.core.security import create_refresh_token
from app.main import create_app
from app.services.user_service import UserService


pytestmark = pytest.mark.anyio


class StubUserService:
    def __init__(
        self,
        user: SimpleNamespace,
        updated_user: SimpleNamespace | None = None,
        register_error: Exception | None = None,
        authenticate_error: Exception | None = None,
        update_error: Exception | None = None,
    ) -> None:
        """
        Initialize the stub user service with preset responses and optional errors.
        
        Parameters:
            user (SimpleNamespace): The default user object returned by register/authenticate when no error is set.
            updated_user (SimpleNamespace | None): The user object returned by update_profile; defaults to `user` if omitted.
            register_error (Exception | None): Exception to raise from `register` instead of returning `user`.
            authenticate_error (Exception | None): Exception to raise from `authenticate` instead of returning `user`.
            update_error (Exception | None): Exception to raise from `update_profile` instead of returning `updated_user`.
        """
        self._user = user
        self._updated_user = updated_user or user
        self._register_error = register_error
        self._authenticate_error = authenticate_error
        self._update_error = update_error

    async def register(self, data) -> SimpleNamespace:
        """
        Register a user using the provided registration payload or raise a configured error.
        
        Parameters:
            data: The registration payload (kept for interface compatibility with the real service).
        
        Returns:
            user (SimpleNamespace): The stub's configured user object.
        
        Raises:
            Exception: The configured exception stored in `self._register_error`, if set.
        """
        if self._register_error:
            raise self._register_error
        return self._user

    async def authenticate(self, email: str, password: str) -> SimpleNamespace:
        """
        Authenticate a user using the provided email and password.
        
        Returns:
            SimpleNamespace: The authenticated user object.
        
        Raises:
            Exception: The configured authentication error when authentication is set to fail.
        """
        if self._authenticate_error:
            raise self._authenticate_error
        return self._user

    async def update_profile(self, user_id, data) -> SimpleNamespace:
        """
        Update a user's profile with the provided data.
        
        Parameters:
            user_id: Identifier of the user to update.
            data: Mapping of profile fields to update.
        
        Returns:
            SimpleNamespace: The updated user object.
        
        Raises:
            Exception: The configured update error if the stub is set to fail.
        """
        if self._update_error:
            raise self._update_error
        return self._updated_user


class InMemoryRefreshTokenStore:
    def __init__(self) -> None:
        """
        Initialize an in-memory refresh token store.
        
        Creates an internal mapping from refresh token (string) to subject (string) used by tests to simulate storing, retrieving, and revoking refresh tokens.
        """
        self._tokens: dict[str, str] = {}

    async def store(self, token: str, subject: str, expires_in) -> None:
        """
        Store the given refresh token and associate it with the subject in the in-memory store.
        
        Parameters:
            token (str): The refresh token to store.
            subject (str): The subject (typically a user id) associated with the token.
            expires_in: Expiration interval for the token; accepted for interface compatibility but ignored by this in-memory implementation.
        """
        self._tokens[token] = subject

    async def get_subject(self, token: str) -> str | None:
        """
        Retrieve the subject associated with a stored refresh token.
        
        Parameters:
            token (str): The refresh token string to look up.
        
        Returns:
            subject (str | None): The subject (typically a user id) mapped to the token, or `None` if the token is not stored.
        """
        return self._tokens.get(token)

    async def revoke(self, token: str) -> None:
        """
        Remove a refresh token from the in-memory store.
        
        Parameters:
            token (str): The refresh token to revoke; if the token is not present, the call has no effect.
        """
        self._tokens.pop(token, None)


class FailingRefreshTokenStore:
    def __init__(self, error: Exception | None = None) -> None:
        """
        Create a failing refresh-token store that raises a configured error on operations.
        
        Parameters:
            error (Exception | None): Exception to raise from store operations. If omitted, defaults to `RedisError("Redis unavailable")`.
        """
        self._error = error or RedisError("Redis unavailable")

    async def store(self, token: str, subject: str, expires_in) -> None:
        """
        Simulates storing a refresh token but always raises the configured error.
        
        Parameters:
            token (str): The refresh token string to store.
            subject (str): The subject (usually user id) associated with the token.
            expires_in: Time until the token expires (e.g., seconds or timedelta).
        
        Raises:
            Exception: The configured error stored in the instance (self._error).
        """
        raise self._error

    async def get_subject(self, token: str) -> str | None:
        """
        Retrieve the subject identifier associated with a refresh token from the store.
        
        Parameters:
            token (str): The refresh token to look up.
        
        Returns:
            str | None: The subject identifier if the token is present, otherwise None.
        
        Raises:
            Exception: The configured store error (stored in `self._error`) to simulate an unavailable refresh-token store.
        """
        raise self._error

    async def revoke(self, token: str) -> None:
        """
        Simulate revoking a refresh token by always raising the configured error.
        
        Raises:
            Exception: The store's configured error instance is raised when called.
        """
        raise self._error


class StubAuthAuditLogService:
    def __init__(self) -> None:
        """
        Initialize the stub audit log service and prepare an empty list to store recorded audit events.
        
        The list is exposed as `self.calls` and is populated with dict entries when audit events are inserted.
        """
        self.calls: list[dict] = []

    async def insert_event(
        self,
        *,
        user_id,
        event,
        ip_address=None,
        user_agent=None,
        refresh_token_hash=None,
    ) -> None:
        """
        Record an authentication audit event into the stub's in-memory call list.
        
        Parameters:
            user_id: The identifier of the user associated with the event.
            event: A short string describing the audit event (e.g., "login", "logout", "register").
            ip_address: Optional client IP address that originated the event.
            user_agent: Optional client user-agent string.
            refresh_token_hash: Optional SHA-256 hex digest of a refresh token associated with the event.
        """
        self.calls.append(
            {
                "user_id": user_id,
                "event": event,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "refresh_token_hash": refresh_token_hash,
            }
        )


def build_user(**overrides) -> SimpleNamespace:
    """
    Create a SimpleNamespace representing a user with sensible default fields, optionally overridden.
    
    Parameters:
        overrides: Keyword arguments to replace default user fields (e.g., `id`, `email`, `full_name`, `is_active`, `created_at`, `role`).
    
    Returns:
        SimpleNamespace: A user-like object with attributes set from the defaults updated by `overrides`.
    """
    payload = {
        "id": uuid4(),
        "email": "user@example.com",
        "full_name": "Test User",
        "is_active": True,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "role": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def reset_limiter_state() -> None:
    """
    Reset the application's rate limiter storage state when the storage exposes a reset or clear method.
    
    This calls `reset()` on the limiter storage if available; otherwise calls `clear()` if available. No action is taken if neither method exists.
    """
    storage = limiter._storage
    reset = getattr(storage, "reset", None)
    if callable(reset):
        reset()
        return
    clear = getattr(storage, "clear", None)
    if callable(clear):
        clear()


@pytest.fixture
def refresh_token_store() -> InMemoryRefreshTokenStore:
    """
    Provide a fresh in-memory refresh-token store for tests.
    
    Returns:
        InMemoryRefreshTokenStore: An in-memory store mapping refresh token strings to subject identifiers used by test cases.
    """
    return InMemoryRefreshTokenStore()


@pytest.fixture
def audit_service_stub() -> StubAuthAuditLogService:
    """
    Provides a stubbed authentication audit-log service for tests.
    
    Returns:
        StubAuthAuditLogService: An in-memory stub that records inserted audit events.
    """
    return StubAuthAuditLogService()


@pytest.fixture
def app(
    refresh_token_store: InMemoryRefreshTokenStore,
    audit_service_stub: StubAuthAuditLogService,
) -> FastAPI:
    """
    Create a FastAPI test application with the refresh-token store and audit service dependencies overridden.
    
    Resets rate-limiter state, creates the application via create_app(), overrides the auth router dependencies to use the provided in-memory refresh token store and audit log stub, and clears those overrides after the caller finishes using the yielded app.
    
    Parameters:
        refresh_token_store (InMemoryRefreshTokenStore): In-memory store to be used for refresh-token dependency.
        audit_service_stub (StubAuthAuditLogService): Stub audit-log service to be used for audit dependency.
    
    Returns:
        FastAPI: A FastAPI application instance with the specified dependency overrides applied.
    """
    reset_limiter_state()
    app = create_app()
    app.dependency_overrides[auth_router.get_refresh_token_store] = lambda: refresh_token_store
    app.dependency_overrides[auth_router.get_auth_audit_log_service] = (
        lambda: audit_service_stub
    )
    yield app
    app.dependency_overrides.clear()


def override_services(
    app: FastAPI,
    auth_service: UserService | None = None,
    users_service: UserService | None = None,
    current_user: SimpleNamespace | None = None,
) -> None:
    """
    Override FastAPI dependency providers to return supplied test doubles for auth, users, and current-user resolution.
    
    If a non-None value is passed for a parameter, this function sets an entry in app.dependency_overrides so the corresponding dependency returns that value for the duration of the test. This mutates app.dependency_overrides in place.
    
    Parameters:
        app (FastAPI): The application whose dependency overrides will be modified.
        auth_service (UserService | None): If provided, overrides auth_router.get_user_service to return this service.
        users_service (UserService | None): If provided, overrides users_router.get_user_service to return this service.
        current_user (SimpleNamespace | None): If provided, overrides get_current_user to return this user.
    """
    if auth_service is not None:
        app.dependency_overrides[auth_router.get_user_service] = lambda: auth_service
    if users_service is not None:
        app.dependency_overrides[users_router.get_user_service] = lambda: users_service
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user


# Register returns a valid user payload.
async def test_register_returns_user(app: FastAPI, audit_service_stub: StubAuthAuditLogService) -> None:
    # Arrange: override the service to return a known user.
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: submit registration payload.
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "full_name": "Test User",
                "password": "Password1",
            },
        )

    # Assert: response payload matches the created user.
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == user.email
    assert body["full_name"] == user.full_name
    assert body["is_active"] is True
    assert body["is_admin"] is False
    assert "created_at" in body

    assert len(audit_service_stub.calls) == 1
    assert audit_service_stub.calls[0]["event"] == "register"
    assert audit_service_stub.calls[0]["user_id"] == user.id


# Login issues access and refresh tokens.
async def test_login_returns_tokens(app: FastAPI, audit_service_stub: StubAuthAuditLogService) -> None:
    # Arrange: override the service to return a known user.
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: submit login credentials.
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )

    # Assert: tokens are issued.
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    assert len(audit_service_stub.calls) == 1
    assert audit_service_stub.calls[0]["event"] == "login"
    assert audit_service_stub.calls[0]["user_id"] == user.id
    expected_hash = hashlib.sha256(body["refresh_token"].encode("utf-8")).hexdigest()
    assert audit_service_stub.calls[0]["refresh_token_hash"] == expected_hash


# Login stores refresh tokens for later validation.
async def test_login_stores_refresh_token(
    app: FastAPI, refresh_token_store: InMemoryRefreshTokenStore
) -> None:
    # Arrange: override the service to return a known user.
    """
    Verifies that a successful login stores the issued refresh token under the issuing user's subject.
    
    Logs in using a stubbed user, extracts the returned refresh token, and asserts the refresh-token store maps that token to the user's id as a string.
    """
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: login and capture the refresh token.
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )

    # Assert: refresh token is stored for the issuing subject.
    refresh_token = response.json()["refresh_token"]
    stored_subject = await refresh_token_store.get_subject(refresh_token)
    assert stored_subject == str(user.id)


# Refresh issues a new access token from a refresh token.
async def test_refresh_issues_new_access_token(app: FastAPI) -> None:
    # Arrange: login to obtain a refresh token.
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: login and then refresh.
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )
        refresh_token = login_response.json()["refresh_token"]

        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    # Assert: access token is re-issued and refresh token is preserved.
    assert refresh_response.status_code == 200
    body = refresh_response.json()
    assert body["access_token"]
    assert body["refresh_token"] == refresh_token


# Refresh rejects tokens that are not stored.
async def test_refresh_rejects_unknown_refresh_token(app: FastAPI) -> None:
    # Arrange: create a refresh token without storing it.
    user = build_user()
    refresh_token = create_refresh_token(str(user.id))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: attempt to refresh with an unknown token.
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    # Assert: refresh tokens must exist in storage.
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


# Login returns 503 when the refresh token store is unavailable.
async def test_login_returns_503_when_refresh_store_unavailable(app: FastAPI) -> None:
    # Arrange: override the refresh token store to fail on write.
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)
    app.dependency_overrides[auth_router.get_refresh_token_store] = (
        lambda: FailingRefreshTokenStore()
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: attempt to login.
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )

    # Assert: login reports the refresh store failure.
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "Refresh token store is unavailable. Try again later."


async def test_login_does_not_audit_when_refresh_store_unavailable(
    app: FastAPI, audit_service_stub: StubAuthAuditLogService
) -> None:
    # Arrange: override the service to return a known user and fail on refresh store write.
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)
    app.dependency_overrides[auth_router.get_refresh_token_store] = (
        lambda: FailingRefreshTokenStore()
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert audit_service_stub.calls == []


# Refresh must reject access tokens.
async def test_refresh_rejects_access_token(app: FastAPI) -> None:
    # Arrange: login to obtain an access token.
    """
    Ensures the refresh endpoint rejects access tokens and returns 401.
    
    Logs in to obtain an access token, then calls the refresh endpoint with that token
    as the refresh token and asserts the response is HTTP 401 Unauthorized.
    """
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )
        access_token = login_response.json()["access_token"]

        # Act: attempt to refresh using an access token.
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

    # Assert: access tokens are not accepted at the refresh endpoint.
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


# Refresh returns 503 when the refresh token store is unavailable.
async def test_refresh_returns_503_when_refresh_store_unavailable(app: FastAPI) -> None:
    # Arrange: create a valid refresh token but fail on lookup.
    """
    Verifies the refresh endpoint returns HTTP 503 when the refresh-token store is unavailable.
    
    Configures the app to use a refresh-token store that raises errors, sends a valid refresh token to POST /api/v1/auth/refresh, and asserts the response status is 503 with the detail "Refresh token store is unavailable. Try again later."
    """
    user = build_user()
    refresh_token = create_refresh_token(str(user.id))
    app.dependency_overrides[auth_router.get_refresh_token_store] = (
        lambda: FailingRefreshTokenStore()
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: attempt to refresh.
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    # Assert: refresh reports the refresh store failure.
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "Refresh token store is unavailable. Try again later."


# Logout revokes refresh tokens and prevents future refresh.
async def test_logout_revokes_refresh_token(
    app: FastAPI,
    refresh_token_store: InMemoryRefreshTokenStore,
    audit_service_stub: StubAuthAuditLogService,
) -> None:
    # Arrange: login to obtain a stored refresh token.
    """
    Verifies that logging out revokes the stored refresh token and records a logout audit event.
    
    Logs in to obtain a stored refresh token, calls the logout endpoint with that token, then attempts to refresh using the same token and expects it to be rejected. Asserts the logout endpoint returns 204, the subsequent refresh returns 401, and a single audit event with `event == "logout"` exists containing the user id and the SHA-256 hash of the revoked refresh token.
    """
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Act: logout and then attempt to refresh again.
        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    # Assert: logout succeeds and refresh token is no longer valid.
    assert logout_response.status_code == status.HTTP_204_NO_CONTENT
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED

    logout_calls = [call for call in audit_service_stub.calls if call["event"] == "logout"]
    assert len(logout_calls) == 1
    assert logout_calls[0]["user_id"] == user.id
    expected_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    assert logout_calls[0]["refresh_token_hash"] == expected_hash


# Logout rejects malformed refresh tokens.
async def test_logout_rejects_invalid_token(
    app: FastAPI, audit_service_stub: StubAuthAuditLogService
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "not-a-token"},
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert audit_service_stub.calls == []


# Logout returns 503 when the refresh token store is unavailable.
async def test_logout_returns_503_when_refresh_store_unavailable(
    app: FastAPI, audit_service_stub: StubAuthAuditLogService
) -> None:
    # Arrange: create a valid refresh token but fail on revoke.
    """
    Verify that POST /api/v1/auth/logout responds with 503 and records no audit events when the refresh-token store is unavailable.
    
    Overrides the refresh-token store with a failing implementation, sends a logout request containing a valid refresh token, and asserts the response status is 503 with detail "Refresh token store is unavailable. Try again later." and that the audit service has no recorded calls.
    """
    user = build_user()
    refresh_token = create_refresh_token(str(user.id))
    app.dependency_overrides[auth_router.get_refresh_token_store] = (
        lambda: FailingRefreshTokenStore()
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "Refresh token store is unavailable. Try again later."
    assert audit_service_stub.calls == []


# Refresh rejects revoked tokens.
async def test_refresh_rejects_revoked_token(
    app: FastAPI, refresh_token_store: InMemoryRefreshTokenStore
) -> None:
    # Arrange: login to obtain a stored refresh token.
    """
    Verify that the /api/v1/auth/refresh endpoint rejects a refresh token that has been revoked.
    
    The test logs in to obtain a refresh token, revokes it in the refresh token store, then attempts to exchange it for a new access token and asserts the response is 401 Unauthorized.
    """
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Act: revoke and then attempt to refresh.
        await refresh_token_store.revoke(refresh_token)
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    # Assert: revoked refresh tokens are rejected.
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


# Refresh rejects tokens with a mismatched stored subject.
async def test_refresh_rejects_subject_mismatch(
    app: FastAPI, refresh_token_store: InMemoryRefreshTokenStore
) -> None:
    # Arrange: store a token under a different subject.
    """
    Verify the refresh endpoint rejects a refresh token when the stored subject does not match the token's subject.
    
    This test stores a refresh token under a different user ID and asserts that POST /api/v1/auth/refresh returns HTTP 401 Unauthorized.
    """
    user = build_user()
    other_user = build_user()
    refresh_token = create_refresh_token(str(user.id))
    await refresh_token_store.store(
        refresh_token,
        str(other_user.id),
        timedelta(days=1),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: refresh with a token whose stored subject does not match.
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    # Assert: subject mismatches are rejected.
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


# /me returns the current user profile.
async def test_me_returns_current_user(app: FastAPI) -> None:
    # Arrange: override the current user and authenticate to get a token.
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service, current_user=user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: login, then fetch /me with the token.
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )
        access_token = login_response.json()["access_token"]

        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # Assert: profile matches current user.
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert body["full_name"] == user.full_name


# /me PATCH updates the current user's profile.
async def test_update_me_updates_profile(app: FastAPI) -> None:
    # Arrange: override services and current user.
    user = build_user()
    updated_user = build_user(id=user.id, email=user.email, full_name="New Name")
    auth_service = StubUserService(user)
    users_service = StubUserService(user, updated_user=updated_user)
    override_services(app, auth_service=auth_service, users_service=users_service, current_user=user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: login, then patch /me.
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )
        access_token = login_response.json()["access_token"]

        response = await client.patch(
            "/api/v1/users/me",
            json={"full_name": "New Name"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # Assert: profile update is reflected in response.
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "New Name"


# Login enforces rate limiting after the allowed threshold.
async def test_login_rate_limited(app: FastAPI) -> None:
    # Arrange: override the service and submit multiple logins.
    """
    Verifies the login endpoint enforces rate limiting.
    
    Sends multiple login attempts and asserts that exceeding the configured limit results in a 429 response on the final request.
    """
    user = build_user()
    service = StubUserService(user)
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: exceed the rate limit.
        responses = []
        for _ in range(6):
            responses.append(
                await client.post(
                    "/api/v1/auth/login",
                    data={"username": "user@example.com", "password": "Password1"},
                )
            )

    # Assert: last request is rate limited.
    assert responses[-1].status_code == 429


# Duplicate registration is rejected with 400.
async def test_register_rejects_duplicate_email(app: FastAPI) -> None:
    # Arrange: service raises a duplicate email error.
    user = build_user()
    service = StubUserService(
        user,
        register_error=HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        ),
    )
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: attempt to register with a duplicate email.
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "full_name": "Test User",
                "password": "Password1",
            },
        )

    # Assert: duplicate registration is rejected.
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Invalid registration payload is rejected with validation errors.
async def test_register_rejects_invalid_payload(app: FastAPI) -> None:
    # Arrange: invalid email and weak password fail validation.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: submit invalid payload.
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "full_name": "A",
                "password": "weak",
            },
        )

    # Assert: request is rejected by validation.
    assert response.status_code == 422


# Login rejects missing required fields.
async def test_login_rejects_missing_fields(app: FastAPI) -> None:
    # Arrange: submit login without required fields.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: omit password.
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com"},
        )

    # Assert: request is rejected by validation.
    assert response.status_code == 422


# Login rejects invalid credentials with 401.
async def test_login_rejects_invalid_credentials(
    app: FastAPI, audit_service_stub: StubAuthAuditLogService
) -> None:
    # Arrange: service raises an invalid credential error.
    user = build_user()
    service = StubUserService(
        user,
        authenticate_error=HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ),
    )
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: attempt to login with invalid credentials.
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "wrong"},
        )

    # Assert: invalid credentials return 401.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert audit_service_stub.calls == []


# Login rejects inactive users with 403.
async def test_login_rejects_inactive_user(app: FastAPI) -> None:
    # Arrange: service raises an inactive user error.
    """
    Verifies that attempting to log in with an inactive user is rejected.
    
    Sends a POST request to /api/v1/auth/login using credentials for a user whose authentication raises a 403 "User is inactive." error and asserts the response status is 403 Forbidden.
    """
    user = build_user()
    service = StubUserService(
        user,
        authenticate_error=HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive.",
        ),
    )
    override_services(app, auth_service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: attempt to login with an inactive user.
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "Password1"},
        )

    # Assert: inactive users are rejected.
    assert response.status_code == status.HTTP_403_FORBIDDEN


# Refresh rejects malformed tokens with 401.
async def test_refresh_rejects_invalid_token(app: FastAPI) -> None:
    # Arrange: submit a malformed refresh token.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: refresh with an invalid token.
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-token"},
        )

    # Assert: invalid token is rejected.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Refresh rejects tokens missing subject claims.
async def test_refresh_rejects_missing_subject(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: force decode_token to return a payload without subject.
    monkeypatch.setattr(auth_router, "decode_token", lambda token: {})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: refresh with a token missing subject.
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "ignored"},
        )

    # Assert: missing subject is rejected.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# /me rejects unauthenticated requests.
async def test_me_rejects_unauthorized(app: FastAPI) -> None:
    # Arrange: override current user dependency to raise 401.
    """
    Verifies that an unauthenticated request to GET /api/v1/users/me is rejected with HTTP 401.
    
    Overrides the current-user dependency to raise a 401 HTTPException and asserts the endpoint returns 401 Unauthorized.
    """
    async def _raise_unauthorized() -> None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    app.dependency_overrides[get_current_user] = _raise_unauthorized

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: call /me without an authenticated user.
        response = await client.get("/api/v1/users/me")

    # Assert: unauthorized access is rejected.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# /me PATCH rejects invalid update payloads.
async def test_update_me_rejects_invalid_payload(app: FastAPI) -> None:
    # Arrange: override current user and send invalid update data.
    user = build_user()
    override_services(app, current_user=user)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Act: submit invalid update payload.
        response = await client.patch(
            "/api/v1/users/me",
            json={"full_name": "A", "email": "not-an-email"},
        )

    # Assert: validation rejects invalid updates.
    assert response.status_code == 422
