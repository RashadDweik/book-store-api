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
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"{self.key_prefix}:{digest}"

    async def store(self, token: str, subject: str, expires_in: timedelta) -> None:
        ttl_seconds = int(expires_in.total_seconds())
        if ttl_seconds <= 0:
            return
        await self.redis.set(self._key(token), subject, ex=ttl_seconds)

    async def get_subject(self, token: str) -> str | None:
        return await self.redis.get(self._key(token))

    async def revoke(self, token: str) -> None:
        await self.redis.delete(self._key(token))

    async def close(self) -> None:
        await self.redis.close()


def build_refresh_token_store(settings: Settings) -> RefreshTokenStore:
    redis = Redis.from_url(settings.REFRESH_TOKEN_REDIS_URL, decode_responses=True)
    return RefreshTokenStore(redis=redis)
