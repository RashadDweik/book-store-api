"""Run SQL seed files from /app/scripts once after migrations are applied."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg


SEED_MARKER_KEY = "scripts_seed_v1"
SEED_ORDER = [
    "seed_authors.sql",
    "seed_categories.sql",
    "seed_books.sql",
    "seed_book_authors.sql",
    "seed_book_categories.sql",
    "seed_existing_books.sql",
]
SCRIPTS_DIR = Path("/app/scripts")


def to_asyncpg_url(url: str) -> str:
    """Convert SQLAlchemy-style async URL to a Postgres URL asyncpg accepts."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def get_seed_files() -> list[Path]:
    """Return seed files in dependency-safe order, then any extra seed_*.sql files."""
    ordered: list[Path] = []
    seen: set[Path] = set()

    for filename in SEED_ORDER:
        path = SCRIPTS_DIR / filename
        if path.exists():
            ordered.append(path)
            seen.add(path)

    extras = sorted(
        path
        for path in SCRIPTS_DIR.glob("seed_*.sql")
        if path not in seen
    )
    return [*ordered, *extras]


async def ensure_seed_marker_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_bootstrap_state (
            key text PRIMARY KEY,
            value text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


async def is_seeded(conn: asyncpg.Connection) -> bool:
    row = await conn.fetchrow(
        "SELECT value FROM app_bootstrap_state WHERE key = $1",
        SEED_MARKER_KEY,
    )
    return row is not None


async def mark_seeded(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO app_bootstrap_state (key, value)
        VALUES ($1, 'done')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        SEED_MARKER_KEY,
    )


async def run_seeds(database_url: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute("SELECT pg_advisory_lock(287346120)")
        await ensure_seed_marker_table(conn)

        if await is_seeded(conn):
            print("[bootstrap] Seed marker exists; skipping SQL seeds.")
            return

        seed_files = get_seed_files()
        if not seed_files:
            print("[bootstrap] No seed_*.sql files found; nothing to apply.")
            await mark_seeded(conn)
            return

        for seed_file in seed_files:
            sql = seed_file.read_text(encoding="utf-8")
            print(f"[bootstrap] Applying seed file: {seed_file.name}")
            await conn.execute(sql)

        await mark_seeded(conn)
        print("[bootstrap] Seed scripts applied successfully.")
    finally:
        try:
            await conn.execute("SELECT pg_advisory_unlock(287346120)")
        finally:
            await conn.close()


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for seed execution")

    asyncio.run(run_seeds(to_asyncpg_url(database_url)))


if __name__ == "__main__":
    main()