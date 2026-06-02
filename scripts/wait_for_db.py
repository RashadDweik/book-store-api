"""Wait for the configured PostgreSQL database to become available."""

from __future__ import annotations

import asyncio
import os
import time

import asyncpg


def to_asyncpg_url(url: str) -> str:
    """Convert SQLAlchemy-style async URL to a Postgres URL asyncpg accepts."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def wait_for_db(database_url: str, retries: int = 60, delay_seconds: float = 1.0) -> None:
    """Try connecting until the DB accepts connections or retries are exhausted."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            conn = await asyncpg.connect(database_url)
            await conn.close()
            print(f"[bootstrap] Database is reachable (attempt {attempt}/{retries}).")
            return
        except Exception as exc:  # pragma: no cover - runtime readiness behavior
            last_error = exc
            print(f"[bootstrap] DB not ready yet (attempt {attempt}/{retries}): {exc}")
            await asyncio.sleep(delay_seconds)

    raise RuntimeError(f"Database did not become ready in time: {last_error}")


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for DB readiness checks")

    started = time.monotonic()
    asyncio.run(wait_for_db(to_asyncpg_url(database_url)))
    elapsed = time.monotonic() - started
    print(f"[bootstrap] DB readiness check completed in {elapsed:.2f}s")


if __name__ == "__main__":
    main()