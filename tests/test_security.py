from datetime import timedelta

import pytest
from fastapi import HTTPException, status

import app.core.security as security


@pytest.fixture(autouse=True)
def _patched_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security.settings, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(security.settings, "ALGORITHM", "HS256")
    monkeypatch.setattr(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)
    monkeypatch.setattr(security.settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)


# Hashing should be one-way and verify correctly.
def test_hash_and_verify_password() -> None:
    plain = "correct-horse-battery-staple"
    hashed = security.hash_password(plain)

    assert hashed != plain
    assert security.verify_password(plain, hashed) is True
    assert security.verify_password("wrong-password", hashed) is False


# Access tokens should include the subject and expiration.
def test_create_access_token_contains_subject() -> None:
    token = security.create_access_token("user-uuid")
    payload = security.decode_token(token)

    assert payload["sub"] == "user-uuid"
    assert payload["type"] == "access"
    assert "exp" in payload


# Access tokens should respect custom expiry overrides.
def test_create_access_token_custom_expiry() -> None:
    token = security.create_access_token("user-uuid", expires_delta=timedelta(minutes=1))
    payload = security.decode_token(token)

    assert payload["sub"] == "user-uuid"
    assert payload["type"] == "access"
    assert "exp" in payload


# Refresh tokens should include the subject and expiration.
def test_create_refresh_token_contains_subject() -> None:
    token = security.create_refresh_token("user-uuid")
    payload = security.decode_token(token)

    assert payload["sub"] == "user-uuid"
    assert payload["type"] == "refresh"
    assert "exp" in payload


# Invalid tokens should raise an unauthorized error.
def test_decode_token_invalid_raises() -> None:
    with pytest.raises(HTTPException) as exc:
        security.decode_token("not-a-token")

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


# Expired tokens should raise an unauthorized error.
def test_decode_token_expired_raises() -> None:
    token = security.create_access_token("user-uuid", expires_delta=timedelta(seconds=-1))

    with pytest.raises(HTTPException) as exc:
        security.decode_token(token)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
