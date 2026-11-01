"""Unpublish changes only the status; history, pointer, published_at and draft stay (US4)."""

from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_articles_create_edit_list import make_article
from tests.api.test_public_read import PUBLIC, publish_new
from tests.integration.test_publish_lifecycle import edit, publish


async def unpublish(client: httpx.AsyncClient, article_id: int) -> httpx.Response:
    return await client.post(f"/api/v1/articles/{article_id}/unpublish")


async def everything(engine: AsyncEngine, article_id: int) -> dict[str, Any]:
    """Every column of the article row and of all its snapshots (updated_at aside)."""
    async with engine.connect() as conn:
        article = (
            await conn.execute(
                text(
                    "SELECT slug, draft_title, draft_body, draft_tags, draft_version, "
                    "last_version_number, current_published_version_id, published_at, created_at "
                    "FROM articles WHERE id = :a"
                ),
                {"a": article_id},
            )
        ).one()
        versions = (
            await conn.execute(
                text("SELECT * FROM article_versions WHERE article_id = :a ORDER BY id"),
                {"a": article_id},
            )
        ).all()
    return {"article": tuple(article), "versions": [tuple(v) for v in versions]}


async def test_unpublish_sets_the_status_and_changes_nothing_else(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await publish_new(client, "going-away", body="Text")
    await edit(client, article["id"], 2, body="Newer draft")
    before = await everything(engine, article["id"])

    response = await unpublish(client, article["id"])
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "unpublished"
    assert detail["live_version_number"] == 1
    assert detail["published_at"] is not None
    assert detail["draft_version"] == 3
    assert detail["draft_body"] == "Newer draft"

    assert await everything(engine, article["id"]) == before


async def test_the_public_detail_is_404_after_unpublish(client: httpx.AsyncClient) -> None:
    article = await publish_new(client, "hidden-soon")
    assert (await client.get(f"{PUBLIC}/hidden-soon")).status_code == 200
    await unpublish(client, article["id"])
    assert (await client.get(f"{PUBLIC}/hidden-soon")).status_code == 404
    assert (await client.get(PUBLIC)).json() == []


async def test_unpublishing_a_draft_returns_409_not_published(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await make_article(client)
    before = await everything(engine, article["id"])
    response = await unpublish(client, article["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_published"
    assert await everything(engine, article["id"]) == before


async def test_unpublishing_twice_returns_409_the_second_time(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await publish_new(client, "twice")
    assert (await unpublish(client, article["id"])).status_code == 200
    before = await everything(engine, article["id"])
    response = await unpublish(client, article["id"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_published"
    assert await everything(engine, article["id"]) == before


async def test_a_missing_article_returns_404(client: httpx.AsyncClient) -> None:
    assert (await unpublish(client, 999999)).status_code == 404


async def test_no_credentials_returns_401_first(secured_client: httpx.AsyncClient) -> None:
    assert (await unpublish(secured_client, 999999)).status_code == 401


async def test_republishing_after_an_edit_makes_a_new_snapshot_and_keeps_published_at(
    client: httpx.AsyncClient,
) -> None:
    article = await publish_new(client, "comes-back", body="One")
    first_published_at = (await client.get(f"/api/v1/articles/{article['id']}")).json()[
        "published_at"
    ]
    await unpublish(client, article["id"])
    await edit(client, article["id"], 2, body="Two")  # unpublish did not change draft_version

    response = await publish(client, article["id"], 3)
    assert response.status_code == 201
    result = response.json()
    assert result["version_number"] == 2
    assert result["status"] == "published"
    assert result["published_at"] == first_published_at
    assert (await client.get(f"{PUBLIC}/comes-back")).json()["body"] == "Two"
