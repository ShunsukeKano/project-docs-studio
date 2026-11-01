"""Readers see only the live snapshot of published articles (US3)."""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_articles_create_edit_list import make_article
from tests.integration.test_publish_lifecycle import edit, publish

PUBLIC = "/api/v1/public/articles"


async def publish_new(
    client: httpx.AsyncClient, slug: str, title: str = "Title", body: str = "Body", **fields: Any
) -> dict[str, Any]:
    article = await make_article(client, slug, title=title, body=body, **fields)
    response = await publish(client, article["id"], 1)
    assert response.status_code == 201, response.text
    return article


async def test_an_empty_list_returns_an_empty_array(client: httpx.AsyncClient) -> None:
    response = await client.get(PUBLIC)
    assert response.status_code == 200
    assert response.json() == []


async def test_the_list_shows_only_published_articles(client: httpx.AsyncClient) -> None:
    await make_article(client, "only-a-draft")
    await publish_new(client, "live-one", title="Live one", tags=["x", "y"])
    items = (await client.get(PUBLIC)).json()
    assert [i["slug"] for i in items] == ["live-one"]
    assert items[0]["title"] == "Live one"
    assert items[0]["tags"] == ["x", "y"]
    assert items[0]["published_at"]


async def test_the_list_is_newest_publication_first(client: httpx.AsyncClient) -> None:
    await publish_new(client, "first")
    await publish_new(client, "second")
    await publish_new(client, "third")
    assert [i["slug"] for i in (await client.get(PUBLIC)).json()] == ["third", "second", "first"]


async def test_updated_at_is_null_until_the_live_version_is_2_or_more(
    client: httpx.AsyncClient,
) -> None:
    article = await publish_new(client, "versions")
    assert (await client.get(PUBLIC)).json()[0]["updated_at"] is None

    await edit(client, article["id"], 2, body="Changed")
    assert (await publish(client, article["id"], 3)).status_code == 201
    item = (await client.get(PUBLIC)).json()[0]
    detail = (await client.get(f"{PUBLIC}/versions")).json()
    assert item["updated_at"] is not None
    assert item["updated_at"] == detail["live_created_at"]


async def test_limit_offset_and_the_cap(client: httpx.AsyncClient) -> None:
    for slug in ("a", "b", "c"):
        await publish_new(client, slug)
    page = await client.get(PUBLIC, params={"limit": 2, "offset": 1})
    assert [i["slug"] for i in page.json()] == ["b", "a"]
    assert (await client.get(PUBLIC, params={"limit": 101})).status_code == 422
    assert (await client.get(PUBLIC, params={"limit": 0})).status_code == 422


async def test_the_detail_shows_the_live_snapshot(client: httpx.AsyncClient) -> None:
    await publish_new(client, "guide", title="Guide", body="# Live text", tags=["docs"])
    response = await client.get(f"{PUBLIC}/guide")
    assert response.status_code == 200
    page = response.json()
    assert page["slug"] == "guide"
    assert page["title"] == "Guide"
    assert page["body"] == "# Live text"
    assert page["tags"] == ["docs"]
    assert page["published_at"]
    assert page["live_created_at"]


async def test_the_detail_never_shows_the_draft_even_after_it_is_edited(
    client: httpx.AsyncClient,
) -> None:
    article = await publish_new(client, "stable", title="Published title", body="Published body")
    await edit(client, article["id"], 2, title="Draft title", body="Draft body", tags=["draft"])
    page = (await client.get(f"{PUBLIC}/stable")).json()
    assert page["title"] == "Published title"
    assert page["body"] == "Published body"
    assert page["tags"] == []
    listed = (await client.get(PUBLIC)).json()[0]
    assert listed["title"] == "Published title"


async def test_every_kind_of_miss_returns_the_same_404(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await make_article(client, "never-published")
    taken_down = await publish_new(client, "taken-down")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE articles SET status = 'unpublished' WHERE id = :a"),
            {"a": taken_down["id"]},
        )

    slugs = ["never-published", "taken-down", "does-not-exist", "Bad Slug!", "x" * 500, "%2e%2e"]
    responses = [await client.get(f"{PUBLIC}/{slug}") for slug in slugs]
    assert {r.status_code for r in responses} == {404}
    assert len({r.text for r in responses}) == 1
    assert responses[0].json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("path", [PUBLIC, f"{PUBLIC}/anything"])
async def test_public_routes_do_not_need_credentials(
    secured_client: httpx.AsyncClient, path: str
) -> None:
    assert (await secured_client.get(path)).status_code in (200, 404)
