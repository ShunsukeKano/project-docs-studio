"""Delete refuses the protected snapshot, in every state, even if the check is bypassed (US5)."""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.errors import VersionIsLiveError
from app.db.session import create_session_factory
from app.domains.articles import repository, service
from tests.api.test_articles_create_edit_list import make_article
from tests.api.test_versions_history import build_versions, versions_path
from tests.integration.test_publish_lifecycle import edit, publish, snapshots
from tests.integration.test_unpublish import unpublish


async def delete(client: httpx.AsyncClient, article_id: int, number: int) -> httpx.Response:
    return await client.delete(versions_path(article_id, number))


async def test_deleting_the_live_version_returns_409_and_the_row_remains(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "live-delete", 2)
    response = await delete(client, article["id"], 2)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_is_live"
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1, 2]


async def test_it_is_still_refused_after_unpublish(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "unpublished-delete", 2)
    await unpublish(client, article["id"])
    response = await delete(client, article["id"], 2)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_is_live"
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1, 2]


async def test_an_older_version_deletes_with_204(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "older-delete", 2)
    response = await delete(client, article["id"], 1)
    assert response.status_code == 204
    assert response.content == b""
    assert [s[0] for s in await snapshots(engine, article["id"])] == [2]
    assert (await client.get(versions_path(article["id"], 1))).status_code == 404


async def test_a_missing_number_returns_404(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "missing-number", 1)
    assert (await delete(client, article["id"], 99)).status_code == 404
    assert (await delete(client, 999999, 1)).status_code == 404


async def test_a_deleted_number_is_never_reused(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "no-reuse", 2)
    assert (await delete(client, article["id"], 1)).status_code == 204
    detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    updated = await edit(client, article["id"], detail["draft_version"], body="Newer")
    response = await publish(client, article["id"], updated["draft_version"])
    assert response.json()["version_number"] == 3  # not 1, and not 2 again
    assert [s[0] for s in await snapshots(engine, article["id"])] == [2, 3]


async def test_a_foreign_key_violation_is_mapped_to_the_same_409(
    client: httpx.AsyncClient, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the service check were bypassed, the database still refuses, and the answer is 409."""
    article = await build_versions(client, "fk-backstop", 2)
    original = repository.lock_article_for_publish

    async def lying_lock(session: Any, article_id: int) -> Any:
        target = await original(session, article_id)
        assert target is not None
        return target._replace(live_version_number=None)  # pretends nothing is live

    monkeypatch.setattr(repository, "lock_article_for_publish", lying_lock)
    sessions = create_session_factory(engine)
    async with sessions() as session:
        with pytest.raises(VersionIsLiveError):
            await service.delete_version(session, article["id"], 2)
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1, 2]


async def test_the_pointer_never_dangles(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    article = await build_versions(client, "dangling", 3)
    await delete(client, article["id"], 1)
    await delete(client, article["id"], 2)
    await delete(client, article["id"], 3)  # refused
    async with engine.connect() as conn:
        count = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM articles a JOIN article_versions v "
                    "ON v.id = a.current_published_version_id WHERE a.id = :a"
                ),
                {"a": article["id"]},
            )
        ).scalar_one()
    assert count == 1


async def test_no_credentials_returns_401_first(secured_client: httpx.AsyncClient) -> None:
    assert (await secured_client.delete(versions_path(999999, 1))).status_code == 401


async def test_a_never_published_article_has_no_version_to_delete(
    client: httpx.AsyncClient,
) -> None:
    article = await make_article(client)
    assert (await delete(client, article["id"], 1)).status_code == 404
