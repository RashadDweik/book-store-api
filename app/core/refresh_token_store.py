"""Refresh token storage backed by Redis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import hashlib

from redis.asyncio import Redis

from app.core.config import Settings


@dataclass
class RefreshTokenStore:
    redis: Redis
    key_prefix: str = "refresh"

    def _key(self, token: str) -> str:
        """
        Compute the Redis key for a refresh token by SHA-256 hashing the token and prefixing it.
        
        Parameters:
            token (str): The refresh token to hash.
        
        Returns:
            str: Redis key in the form "<key_prefix>:<hexdigest>" where <hexdigest> is the SHA-256 hex digest of the UTF-8 encoded token.
        """
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"{self.key_prefix}:{digest}"

    async def store(self, token: str, subject: str, expires_in: timedelta) -> None:
        """
        Store a subject under a Redis key derived from the given refresh token and set its expiration.
        
        If `expires_in` is zero or negative, the function does nothing.
        
        Parameters:
            token (str): The raw refresh token used to compute the Redis key.
            subject (str): The subject identifier to store (e.g., user id).
            expires_in (timedelta): Time-to-live for the key; converted to whole seconds for Redis.
        """
        ttl_seconds = int(expires_in.total_seconds())
        if ttl_seconds <= 0:
            return
        await self.redis.set(self._key(token), subject, ex=ttl_seconds)

    async def get_subject(self, token: str) -> str | None:
        """
        Retrieve the subject associated with a refresh token.
        
        Parameters:
            token (str): The refresh token string to look up.
        
        Returns:
            str or None: The stored subject for the token, or `None` if the token is not found.
        """
        return await self.redis.get(self._key(token))

    async def revoke(self, token: str) -> None:
        """
        Delete the refresh token's entry from Redis, removing any stored subject and its expiration.
        
        Parameters:
            token (str): The refresh token to revoke; the token string is hashed to compute the Redis key used for deletion.
        """
        await self.redis.delete(self._key(token))

    async def close(self) -> None:
        """
        Close the underlying Redis client connection.
        
        After this method completes, the store's Redis client is closed and must not be used for further operations.
        """
        await self.redis.close()


def build_refresh_token_store(settings: Settings) -> RefreshTokenStore:
    """
    Create a RefreshTokenStore backed by an async Redis client configured from application settings.
    
    Parameters:
        settings (Settings): Application settings that must provide `REFRESH_TOKEN_REDIS_URL`.
    
    Returns:
        RefreshTokenStore: Store initialized with a Redis client created from `settings.REFRESH_TOKEN_REDIS_URL` (client uses `decode_responses=True`).
    """
    redis = Redis.from_url(settings.REFRESH_TOKEN_REDIS_URL, decode_responses=True)
    return RefreshTokenStore(redis=redis)
