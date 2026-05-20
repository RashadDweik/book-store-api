"""Security helpers for password hashing and JWT handling."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError , jwt
from passlib.context import CryptContext

from app.core.config import get_settings


settings = get_settings()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    # Hash a plaintext password using the configured context.
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    # Check a plaintext password against a stored hash.
    return _pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    # Build a JWT access token with subject and expiration.
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire_at = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire_at}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    # Build a longer-lived JWT refresh token for the subject.
    expire_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire_at}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    # Decode a JWT and raise an HTTP 401 if invalid or expired.
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
