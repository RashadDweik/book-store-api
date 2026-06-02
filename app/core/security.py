"""Security helpers for password hashing and JWT handling."""

from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException, status
from jose import JWTError , jwt
from passlib.context import CryptContext
import hashlib
import bcrypt

from app.core.config import get_settings


settings = get_settings()
# Use bcrypt_sha256 to avoid the 72-byte input limit of raw bcrypt.
# Keep plain bcrypt in the list so previously-stored bcrypt hashes still verify.
_pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")

# Initialize Passlib's bcrypt backend with a short test secret at import time.
# This forces backend detection to run on a safe (short) value so later calls
# that pass long passwords won't trigger the backend probe which uses the
# provided secret and can raise a 72-byte error.
try:  # pragma: no cover - runtime-only safety initialization
    _pwd_context.hash("_passlib_init_", scheme="bcrypt")
except Exception:
    # If backend initialization fails for any reason, avoid breaking import.
    pass


def hash_password(plain: str) -> str:
    # Hash a plaintext password using the configured context.
    # Force `bcrypt_sha256` to ensure inputs >72 bytes are handled safely
    # (bcrypt_sha256 pre-hashes with SHA-256 before calling bcrypt).
    try:
        return _pwd_context.hash(plain, scheme="bcrypt_sha256")
    except ValueError as exc:
        # Fallback: manually SHA-256 the secret and bcrypt the digest.
        # This produces a bcrypt hash of the 32-byte digest, equivalent to
        # what bcrypt_sha256 does under the hood and avoids passlib's
        # backend probe that may use the long secret.
        digest = hashlib.sha256(plain.encode("utf-8")).digest()
        return bcrypt.hashpw(digest, bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    # Check a plaintext password against a stored hash.
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        # Fallback verification for manually-created bcrypt-of-sha256 hashes.
        try:
            digest = hashlib.sha256(plain.encode("utf-8")).digest()
            return bcrypt.checkpw(digest, hashed.encode())
        except Exception:
            return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    # Build a JWT access token with subject and expiration.
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire_at = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "type": "access", "exp": expire_at}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    # Build a longer-lived JWT refresh token for the subject.
    expire_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expire_at,
        "jti": str(uuid.uuid4()),
    }
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
