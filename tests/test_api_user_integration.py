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
        self._user = user
        self._updated_user = updated_user or user
        self._register_error = register_error
        self._authenticate_error = authenticate_error
        self._update_error = update_error

    async def register(self, data) -> SimpleNamespace:
        if self._register_error:
            raise self._register_error
        return self._user

    async def authenticate(self, email: str, password: str) -> SimpleNamespace:
        if self._authenticate_error:
            raise self._authenticate_error
        return self._user

    async def update_profile(self, user_id, data) -> SimpleNamespace:
        if self._update_error:
            raise self._update_error
        return self._updated_user


class InMemoryRefreshTokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    async def store(self, token: str, subject: str, expires_in) -> None:
        self._tokens[token] = subject

    async def get_subject(self, token: str) -> str | None:
        return self._tokens.get(token)

    async def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)


class FailingRefreshTokenStore:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or RedisError("Redis unavailable")

    async def store(self, token: str, subject: str, expires_in) -> None:
        raise self._error

    async def get_subject(self, token: str) -> str | None:
        raise self._error

    async def revoke(self, token: str) -> None:
        raise self._error


class StubAuthAuditLogService:
    def __init__(self) -> None:
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





@pytest.fixture
def refresh_token_store() -> InMemoryRefreshTokenStore:
    return InMemoryRefreshTokenStore()


@pytest.fixture
def audit_service_stub() -> StubAuthAuditLogService:
    return StubAuthAuditLogService()


@pytest.fixture
def app(
    refresh_token_store: InMemoryRefreshTokenStore,
    audit_service_stub: StubAuthAuditLogService,
) -> FastAPI:
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
    assert "refresh_token" not in body

    refresh_cookie = response.cookies.get(auth_router.settings.REFRESH_COOKIE_NAME)
    assert refresh_cookie
    assert "HttpOnly" in response.headers.get("set-cookie", "")

    assert len(audit_service_stub.calls) == 1
    assert audit_service_stub.calls[0]["event"] == "login"
    assert audit_service_stub.calls[0]["user_id"] == user.id
    expected_hash = hashlib.sha256(refresh_cookie.encode("utf-8")).hexdigest()
    assert audit_service_stub.calls[0]["refresh_token_hash"] == expected_hash


# Login stores refresh tokens for later validation.
async def test_login_stores_refresh_token(
    app: FastAPI, refresh_token_store: InMemoryRefreshTokenStore
) -> None:
    # Arrange: override the service to return a known user.
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

    # Assert: refresh token cookie is stored for the issuing subject.
    refresh_token = response.cookies.get(auth_router.settings.REFRESH_COOKIE_NAME)
    assert refresh_token
    stored_subject = await refresh_token_store.get_subject(refresh_token)
    assert stored_subject == str(user.id)


# Refresh issues a new access token and rotates the refresh token.
async def test_refresh_issues_new_access_token(
    app: FastAPI, refresh_token_store: InMemoryRefreshTokenStore
) -> None:
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
        refresh_token = login_response.cookies.get(auth_router.settings.REFRESH_COOKIE_NAME)
        assert refresh_token

        refresh_response = await client.post(
            "/api/v1/auth/refresh",
        )

    # Assert: access token is re-issued and refresh token is rotated.
    assert refresh_response.status_code == 200
    body = refresh_response.json()
    assert body["access_token"]
    assert "refresh_token" not in body

    rotated_refresh_token = refresh_response.cookies.get(auth_router.settings.REFRESH_COOKIE_NAME)
    assert rotated_refresh_token
    assert rotated_refresh_token != refresh_token
    assert await refresh_token_store.get_subject(rotated_refresh_token) == str(user.id)
    assert await refresh_token_store.get_subject(refresh_token) is None


# Refresh rejects tokens that are not stored.
async def test_refresh_rejects_unknown_refresh_token(app: FastAPI) -> None:
    # Arrange: create a refresh token without storing it.
    user = build_user()
    refresh_token = create_refresh_token(str(user.id))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        client.cookies.set(
            auth_router.settings.REFRESH_COOKIE_NAME,
            refresh_token,
            domain="test",
            path=auth_router.settings.REFRESH_COOKIE_PATH,
        )
        # Act: attempt to refresh with an unknown token.
        refresh_response = await client.post("/api/v1/auth/refresh")

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
        client.cookies.clear()
        client.cookies.set(auth_router.settings.REFRESH_COOKIE_NAME, access_token)
        refresh_response = await client.post("/api/v1/auth/refresh")

    # Assert: access tokens are not accepted at the refresh endpoint.
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


# Refresh returns 503 when the refresh token store is unavailable.
async def test_refresh_returns_503_when_refresh_store_unavailable(app: FastAPI) -> None:
    # Arrange: create a valid refresh token but fail on lookup.
    user = build_user()
    refresh_token = create_refresh_token(str(user.id))
    app.dependency_overrides[auth_router.get_refresh_token_store] = (
        lambda: FailingRefreshTokenStore()
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        client.cookies.set(auth_router.settings.REFRESH_COOKIE_NAME, refresh_token)
        # Act: attempt to refresh.
        response = await client.post("/api/v1/auth/refresh")

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
        refresh_token = login_response.cookies.get(auth_router.settings.REFRESH_COOKIE_NAME)
        assert refresh_token

        # Act: logout and then attempt to refresh again.
        logout_response = await client.post("/api/v1/auth/logout")
        refresh_response = await client.post("/api/v1/auth/refresh")

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
        client.cookies.set(
            auth_router.settings.REFRESH_COOKIE_NAME,
            "not-a-token",
            domain="test",
            path=auth_router.settings.REFRESH_COOKIE_PATH,
        )
        response = await client.post("/api/v1/auth/logout")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert audit_service_stub.calls == []


# Logout returns 503 when the refresh token store is unavailable.
async def test_logout_returns_503_when_refresh_store_unavailable(
    app: FastAPI, audit_service_stub: StubAuthAuditLogService
) -> None:
    # Arrange: create a valid refresh token but fail on revoke.
    user = build_user()
    refresh_token = create_refresh_token(str(user.id))
    app.dependency_overrides[auth_router.get_refresh_token_store] = (
        lambda: FailingRefreshTokenStore()
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        client.cookies.set(auth_router.settings.REFRESH_COOKIE_NAME, refresh_token)
        response = await client.post("/api/v1/auth/logout")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "Refresh token store is unavailable. Try again later."
    assert audit_service_stub.calls == []


# Refresh rejects revoked tokens.
async def test_refresh_rejects_revoked_token(
    app: FastAPI, refresh_token_store: InMemoryRefreshTokenStore
) -> None:
    # Arrange: login to obtain a stored refresh token.
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
        refresh_token = login_response.cookies.get(auth_router.settings.REFRESH_COOKIE_NAME)
        assert refresh_token

        # Act: revoke and then attempt to refresh.
        await refresh_token_store.revoke(refresh_token)
        refresh_response = await client.post("/api/v1/auth/refresh")

    # Assert: revoked refresh tokens are rejected.
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


# Refresh rejects tokens with a mismatched stored subject.
async def test_refresh_rejects_subject_mismatch(
    app: FastAPI, refresh_token_store: InMemoryRefreshTokenStore
) -> None:
    # Arrange: store a token under a different subject.
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
        client.cookies.set(
            auth_router.settings.REFRESH_COOKIE_NAME,
            refresh_token,
            domain="test",
            path=auth_router.settings.REFRESH_COOKIE_PATH,
        )
        # Act: refresh with a token whose stored subject does not match.
        refresh_response = await client.post("/api/v1/auth/refresh")

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
        client.cookies.set(
            auth_router.settings.REFRESH_COOKIE_NAME,
            "not-a-token",
            domain="test",
            path=auth_router.settings.REFRESH_COOKIE_PATH,
        )
        # Act: refresh with an invalid token.
        response = await client.post("/api/v1/auth/refresh")

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
        client.cookies.set(
            auth_router.settings.REFRESH_COOKIE_NAME,
            "ignored",
            domain="test",
            path=auth_router.settings.REFRESH_COOKIE_PATH,
        )
        # Act: refresh with a token missing subject.
        response = await client.post("/api/v1/auth/refresh")

    # Assert: missing subject is rejected.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# /me rejects unauthenticated requests.
async def test_me_rejects_unauthorized(app: FastAPI) -> None:
    # Arrange: override current user dependency to raise 401.
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
