"""Shared fixtures. The guard runs first: nothing here touches a database it does not trust."""

import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import Settings
from app.db.session import create_session_factory
from app.main import create_app
from tests.db_guard import UnsafeTestDatabaseError, assert_safe_test_database

BACKEND_DIR = Path(__file__).resolve().parents[1]

# The suite must not depend on a developer's local .env: it can never switch the AI extra on or
# hand a real key to any test (environment variables beat the .env file in the settings).
for _name, _value in {
    "AI_ENABLED": "false",
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_MODEL": "claude-sonnet-4-6",
}.items():
    os.environ[_name] = _value


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    extra = frozenset(
        host.strip()
        for host in os.environ.get("TEST_DATABASE_EXTRA_HOSTS", "").split(",")
        if host.strip()
    )
    assert_safe_test_database(url, extra)  # raises before any connection is made
    assert url is not None
    return url


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "tests/integration/" in item.nodeid:
            item.add_marker(pytest.mark.db)


@pytest.fixture(scope="session")
def database_url() -> str:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL is not set, so the database tests cannot run")
    try:
        return _test_database_url()
    except UnsafeTestDatabaseError as exc:
        # An unsafe URL stops the whole run: it is never skipped quietly.
        pytest.exit(f"unsafe test database: {exc}", returncode=2)


@pytest.fixture(scope="session")
def database(database_url: str) -> str:
    """Apply the schema once per session (downgrade first, so a stale schema is never reused)."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = database_url
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return database_url


@pytest_asyncio.fixture
async def engine(database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database, pool_size=3)
    # Reset before each test. Both tables go in one statement because they reference each other;
    # the snapshot table's TRUNCATE guard allows it only under this transaction-local setting.
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL docs.allow_reset = 'on'"))
        await connection.execute(text("TRUNCATE articles, article_versions RESTART IDENTITY"))
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def connection_factory(engine: AsyncEngine) -> Callable[[], AsyncConnection]:
    """Separate connections (the pool holds at least 2) for the concurrency tests."""
    return engine.connect


# ---------------------------------------------------------------------------
# API fixtures: the real app, wired to the _test database (the lifespan is not run by the
# test transport, so the session factory is set here).
# ---------------------------------------------------------------------------
TEST_WRITER_USER = "writer"
TEST_WRITER_PASSWORD = "local-test-only"  # a test value for a local app, never a real credential


def _build_app(engine: AsyncEngine, *, authentication: bool) -> FastAPI:
    settings = Settings(
        env="local",
        basic_auth_enabled=authentication,
        basic_auth_user=TEST_WRITER_USER if authentication else "",
        basic_auth_password=SecretStr(TEST_WRITER_PASSWORD if authentication else ""),
    )
    app = create_app(settings)
    app.state.session_factory = create_session_factory(engine)
    return app


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """A client for the app with the writer login off (the local default)."""
    transport = httpx.ASGITransport(app=_build_app(engine, authentication=False))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest_asyncio.fixture
async def secured_client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """A client for the app with the writer login on. It sends no credentials by default."""
    transport = httpx.ASGITransport(app=_build_app(engine, authentication=True))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
