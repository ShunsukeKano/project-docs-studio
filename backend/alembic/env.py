"""Alembic environment: runs migrations through an async engine."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import load_settings

config = context.config


def _database_url() -> str:
    # A caller (the test suite) can pass a URL through config.attributes; otherwise DATABASE_URL.
    url = config.attributes.get("database_url") or load_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return str(url)


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline mode is not supported: the schema file needs a live connection")
asyncio.run(_run_online())
