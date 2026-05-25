"""Shared rate limiter instance."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


settings = get_settings()
limiter = Limiter(
	key_func=get_remote_address,
	default_limits=["100/minute"],
	storage_uri=settings.RATE_LIMIT_STORAGE_URI,
)
