"""Application configuration loaded from environment variables."""

from functools import lru_cache

from urllib.parse import urlsplit, urlunsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings with defaults for local development."""
    APP_NAME: str = "BookShop API"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "FastAPI book store API"
    DEBUG: bool = False
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str = "redis://localhost:6379"
    REFRESH_TOKEN_REDIS_URL: str = "redis://localhost:6381"
    REDIS_REFRESH_PASSWORD: str | None = None
    RATE_LIMIT_STORAGE_URI: str = "redis://localhost:6380"
    SENTRY_DSN: str = ""
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Load from .env during local development and ignore unknown variables.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _apply_refresh_redis_password(self) -> "Settings":
        """
        Embed REDIS_REFRESH_PASSWORD into REFRESH_TOKEN_REDIS_URL when applicable.
        
        If REDIS_REFRESH_PASSWORD is set and REFRESH_TOKEN_REDIS_URL was not explicitly provided, updates REFRESH_TOKEN_REDIS_URL to include the password in the URL's authority component while preserving the scheme, host, port, and path. If the original URL omits host, defaults to "localhost"; if it omits path, defaults to "/0".
        
        Returns:
            self (Settings): The settings instance, possibly with REFRESH_TOKEN_REDIS_URL modified.
        """
        if not self.REDIS_REFRESH_PASSWORD:
            return self
        if "REFRESH_TOKEN_REDIS_URL" in self.model_fields_set:
            return self

        parts = urlsplit(self.REFRESH_TOKEN_REDIS_URL)
        host = parts.hostname or "localhost"
        port = f":{parts.port}" if parts.port else ""
        path = parts.path or "/0"
        netloc = f":{self.REDIS_REFRESH_PASSWORD}@{host}{port}"
        self.REFRESH_TOKEN_REDIS_URL = urlunsplit((parts.scheme or "redis", netloc, path, "", ""))
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Get the application's cached Settings instance.
    
    Returns:
        settings (Settings): The loaded Settings object, cached to avoid re-parsing environment variables.
    """
    return Settings()
