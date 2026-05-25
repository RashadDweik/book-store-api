"""Application configuration loaded from environment variables."""

from functools import lru_cache

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
    RATE_LIMIT_STORAGE_URI: str = "redis://localhost:6380"
    SENTRY_DSN: str = ""
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Load from .env during local development and ignore unknown variables.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance to avoid repeated env parsing."""
    return Settings()
