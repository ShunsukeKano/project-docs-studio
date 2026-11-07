"""A request that cannot get the article row lock in time answers 503 `busy`, never a bare 500."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domains.articles import service
from tests.api.test_versions_history import build_versions
from tests.integration.test_delete_version import delete
from tests.integration.test_publish_lifecycle import publish, snapshots
from tests.integration.test_unpublish import unpublish


@pytest.fixture(autouse=True)
def short_lock_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wait 100 ms instead of 3 s so the test is quick; the code path is otherwise the same."""

    async def quick(session: AsyncSession) -> None:
        await session.execute(text("SET LOCAL lock_timeout = '100ms'"))

    monkeypatch.setattr(service, "set_lock_timeout", quick)


@asynccontextmanager
async def holding_the_row_lock(engine: AsyncEngine, article_id: int) -> AsyncIterator[None]:
    """Another transaction keeps the article row locked, as a slow Publish would."""
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT id FROM articles WHERE id = :a FOR UPDATE"), {"a": article_id}
        )
        try:
            yield
        finally:
            await conn.rollback()


def assert_busy(response: httpx.Response) -> None:
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "busy"
    assert response.headers["Retry-After"] == "1"


async def test_publish_answers_503_and_changes_nothing_then_works_once_free(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "busy-publish", 1)
    detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    patched = await client.patch(
        f"/api/v1/articles/{article['id']}",
        json={"expected_draft_version": detail["draft_version"], "body": "Changed"},
    )
    expected = patched.json()["draft_version"]

    async with holding_the_row_lock(engine, article["id"]):
        assert_busy(await publish(client, article["id"], expected))
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1]

    retry = await publish(client, article["id"], expected)
    assert retry.status_code == 201  # the same request succeeds once the lock is free


async def test_unpublish_answers_503(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    article = await build_versions(client, "busy-unpublish", 1)
    async with holding_the_row_lock(engine, article["id"]):
        assert_busy(await unpublish(client, article["id"]))
    still = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    assert still["status"] == "published"


async def test_delete_version_answers_503(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    article = await build_versions(client, "busy-delete", 2)
    async with holding_the_row_lock(engine, article["id"]):
        assert_busy(await delete(client, article["id"], 1))
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1, 2]
