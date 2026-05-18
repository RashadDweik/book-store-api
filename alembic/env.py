"""Alembic environment configuration for migrations."""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Ensure the app package is importable when Alembic runs from alembic/.
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from app import models  # noqa: E402

config = context.config

DOTENV_PATH = os.path.join(BASE_DIR, ".env")


def load_dotenv(path: str) -> None:
    """Populate os.environ from a .env file without overwriting existing values."""
    if not os.path.exists(path):
        return

    with open(path, "r") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            if not key or not _:
                continue
            if key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


# Load environment variables for migrations (only if not already set).
load_dotenv(DOTENV_PATH)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url() -> str:
    """Return database URL for Alembic, falling back to a local default."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://bookshop:bookshop@localhost:5432/bookshop",
    )


config.set_main_option("sqlalchemy.url", get_database_url())

# Use model metadata so autogenerate can detect schema changes.
target_metadata = models.Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode using a live async DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url, poolclass=pool.NullPool)

    def do_run_migrations(connection) -> None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
