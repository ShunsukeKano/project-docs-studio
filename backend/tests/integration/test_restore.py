"""Restore copies a snapshot into the draft and touches nothing else (US5)."""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_public_read import PUBLIC
from tests.api.test_versions_history import build_versions, versions_path
from tests.integration.test_unpublish import everything, unpublish


async def restore(
    client: httpx.AsyncClient, article_id: int, number: int, expected: int
) -> httpx.Response:
    return await client.post(
        f"{versions_path(article_id, number)}/restore", json={"expected_draft_version": expected}
    )


async def current_draft_version(client: httpx.AsyncClient, article_id: int) -> int:
    detail = (await client.get(f"/api/v1/articles/{article_id}")).json()
    return int(detail["draft_version"])


def without_draft(state: dict[str, Any]) -> dict[str, Any]:
    """The state minus the draft columns and the draft version, which Restore may change."""
    article = state["article"]
    # (slug, draft_title, draft_body, draft_tags, draft_version, last_version_number,
    #  pointer, published_at, created_at)
    return {
        "article": (article[0], article[5], article[6], article[7], article[8]),
        "versions": state["versions"],
    }


@pytest.mark.parametrize("state", ["published", "unpublished"])
async def test_restore_replaces_only_the_draft_and_changes_no_snapshot_or_state(
    client: httpx.AsyncClient, engine: AsyncEngine, state: str
) -> None:
    article = await build_versions(client, f"restore-{state}", 3)
    if state == "unpublished":
        await unpublish(client, article["id"])
    before = await everything(engine, article["id"])
    before_detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    expected = before_detail["draft_version"]

    response = await restore(client, article["id"], 1, expected)

    assert response.status_code == 200
    detail = response.json()
    assert detail["draft_title"] == "Title 1"
    assert detail["draft_body"] == "Body 1"
    assert detail["draft_tags"] == ["t1"]
    assert detail["draft_version"] == expected + 1
    assert detail["status"] == before_detail["status"]
    assert detail["slug"] == before_detail["slug"]
    assert detail["published_at"] == before_detail["published_at"]
    assert detail["live_version_number"] == 3

    after = await everything(engine, article["id"])
    assert without_draft(after) == without_draft(before)  # every snapshot column, state, pointer


async def test_restore_does_not_publish(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "not-published", 2)
    expected = await current_draft_version(client, article["id"])
    await restore(client, article["id"], 1, expected)
    public = (await client.get(f"{PUBLIC}/not-published")).json()
    assert public["title"] == "Title 2"  # still the live snapshot, not the restored draft
    assert (await client.get(f"/api/v1/articles/{article['id']}")).json()[
        "live_version_number"
    ] == 2


async def test_a_stale_version_returns_409_and_changes_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "stale-restore", 2)
    expected = await current_draft_version(client, article["id"])
    before = await everything(engine, article["id"])
    response = await restore(client, article["id"], 1, expected - 1)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    assert response.json()["error"]["details"] == {"current_draft_version": expected}
    assert await everything(engine, article["id"]) == before


async def test_a_missing_version_number_returns_404_and_changes_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "no-number", 2)
    expected = await current_draft_version(client, article["id"])
    before = await everything(engine, article["id"])
    response = await restore(client, article["id"], 99, expected)
    assert response.status_code == 404
    assert await everything(engine, article["id"]) == before


async def test_a_never_published_article_has_nothing_to_restore(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    from tests.api.test_articles_create_edit_list import make_article

    article = await make_article(client)
    before = await everything(engine, article["id"])
    assert (await restore(client, article["id"], 1, 1)).status_code == 404
    assert await everything(engine, article["id"]) == before


async def test_a_missing_article_returns_404_before_validation(client: httpx.AsyncClient) -> None:
    response = await client.post(f"{versions_path(999999, 1)}/restore", json={})
    assert response.status_code == 404


async def test_the_expected_version_is_required(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "needs-version", 1)
    response = await client.post(f"{versions_path(article['id'], 1)}/restore", json={})
    assert response.status_code == 422


async def test_no_credentials_returns_401_first(secured_client: httpx.AsyncClient) -> None:
    response = await secured_client.post(f"{versions_path(1, 1)}/restore", json={})
    assert response.status_code == 401
