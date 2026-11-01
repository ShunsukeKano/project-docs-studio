"""Async engine and session factory. Nothing connects until the first query."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_size=3,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"server_settings": {"timezone": "UTC"}},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def set_lock_timeout(session: AsyncSession) -> None:
    """Bound how long a statement waits for a row lock (applies to the current transaction)."""
    await session.execute(text("SET LOCAL lock_timeout = '3s'"))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:
        raise RuntimeError("DATABASE_URL is not set, so there is no database session")
    async with factory() as session:
        yield session
