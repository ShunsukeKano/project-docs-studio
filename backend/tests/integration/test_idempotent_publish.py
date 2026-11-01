"""Publishing unchanged content creates no snapshot; only the live snapshot is compared (US7)."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_articles_create_edit_list import make_article
from tests.api.test_public_read import PUBLIC, publish_new
from tests.integration.test_publish_lifecycle import edit, publish, snapshots
from tests.integration.test_unpublish import everything, unpublish


async def test_an_unchanged_draft_returns_200_and_creates_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await publish_new(client, "same-again", body="Text")  # draft_version is now 2
    before = await everything(engine, article["id"])

    response = await publish(client, article["id"], 2)

    assert response.status_code == 200
    result = response.json()
    assert result["created"] is False
    assert result["version_number"] == 1
    assert result["status"] == "published"
    assert result["draft_version"] == 2
    assert await everything(engine, article["id"]) == before  # pointer, published_at, counter


async def test_publishing_twice_in_a_row_stays_idempotent(client: httpx.AsyncClient) -> None:
    article = await publish_new(client, "twice")
    first = await publish(client, article["id"], 2)
    second = await publish(client, article["id"], 2)
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json() == second.json()


async def test_an_unpublished_article_with_an_unchanged_draft_goes_back_to_published(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await publish_new(client, "returns", body="Text")
    await unpublish(client, article["id"])
    assert (await client.get(f"{PUBLIC}/returns")).status_code == 404

    response = await publish(client, article["id"], 2)

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["status"] == "published"
    assert (await client.get(f"{PUBLIC}/returns")).status_code == 200
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1]
    detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    assert detail["live_version_number"] == 1
    assert detail["draft_version"] == 2


async def test_a_draft_equal_to_an_older_version_still_creates_a_new_snapshot(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await publish_new(client, "back-to-a", body="A")  # v1 = A, draft_version 2
    await edit(client, article["id"], 2, body="B")
    assert (await publish(client, article["id"], 3)).status_code == 201  # v2 = B, draft_version 4
    await edit(client, article["id"], 4, body="A")  # now equal to v1, which is not live

    response = await publish(client, article["id"], 5)

    assert response.status_code == 201
    assert response.json()["created"] is True
    assert response.json()["version_number"] == 3
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1, 2, 3]


async def test_a_different_tag_order_counts_as_a_change(client: httpx.AsyncClient) -> None:
    article = await publish_new(client, "tag-order", tags=["a", "b"])
    await edit(client, article["id"], 2, tags=["b", "a"])
    response = await publish(client, article["id"], 3)
    assert response.status_code == 201
    assert response.json()["version_number"] == 2


async def test_a_stale_version_returns_409_before_the_idempotent_check(
    client: httpx.AsyncClient,
) -> None:
    article = await publish_new(client, "stale-first")  # unchanged draft, but the version is old
    response = await publish(client, article["id"], 1)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"


async def test_empty_content_returns_422_before_the_idempotent_check(
    client: httpx.AsyncClient,
) -> None:
    article = await publish_new(client, "emptied")
    await edit(client, article["id"], 2, body="")
    response = await publish(client, article["id"], 3)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_content"


async def test_a_never_published_article_is_never_idempotent(client: httpx.AsyncClient) -> None:
    article = await make_article(client, body="Text")
    response = await publish(client, article["id"], 1)
    assert response.status_code == 201
    assert response.json()["created"] is True
