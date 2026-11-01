"""Publish creates numbered snapshots and sets published_at only the first time (US2)."""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_articles_create_edit_list import make_article


async def publish(
    client: httpx.AsyncClient, article_id: int, expected: int, **kwargs: Any
) -> httpx.Response:
    return await client.post(
        f"/api/v1/articles/{article_id}/publish",
        json={"expected_draft_version": expected},
        **kwargs,
    )


async def edit(
    client: httpx.AsyncClient, article_id: int, expected: int, **fields: Any
) -> dict[str, Any]:
    response = await client.patch(
        f"/api/v1/articles/{article_id}", json={"expected_draft_version": expected, **fields}
    )
    assert response.status_code == 200, response.text
    updated: dict[str, Any] = response.json()
    return updated


async def snapshots(engine: AsyncEngine, article_id: int) -> list[tuple[int, str, str]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT version_number, title, body FROM article_versions "
                "WHERE article_id = :a ORDER BY version_number"
            ),
            {"a": article_id},
        )
        return [(r[0], r[1], r[2]) for r in rows]


async def test_the_first_publish_creates_version_1(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await make_article(client, body="Hello")
    response = await publish(client, article["id"], 1)
    assert response.status_code == 201
    result = response.json()
    assert result["created"] is True
    assert result["version_number"] == 1
    assert result["status"] == "published"
    assert result["published_at"] is not None
    assert result["draft_version"] == 2
    assert await snapshots(engine, article["id"]) == [(1, "Intro", "Hello")]

    detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    assert detail["status"] == "published"
    assert detail["live_version_number"] == 1
    assert detail["published_at"] == result["published_at"]
    assert detail["draft_version"] == 2


async def test_the_next_publish_creates_version_2_and_keeps_published_at(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await make_article(client, body="First")
    first = (await publish(client, article["id"], 1)).json()
    await edit(client, article["id"], 2, body="Second")  # draft_version is now 3
    second = await publish(client, article["id"], 3)

    assert second.status_code == 201
    result = second.json()
    assert result["version_number"] == 2
    assert result["published_at"] == first["published_at"]
    assert result["draft_version"] == 4
    detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    assert detail["live_version_number"] == 2
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1, 2]


async def test_numbering_comes_from_the_counter_and_is_never_reused(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await make_article(client, body="v1")
    await publish(client, article["id"], 1)
    await edit(client, article["id"], 2, body="v2")
    await publish(client, article["id"], 3)
    async with engine.begin() as conn:
        counter = (
            await conn.execute(
                text("SELECT last_version_number FROM articles WHERE id = :a"),
                {"a": article["id"]},
            )
        ).scalar_one()
    assert counter == 2


@pytest.mark.parametrize(
    "fields",
    [{"body": ""}, {"body": "   \n"}],
)
async def test_an_empty_body_returns_422_empty_content_and_creates_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine, fields: dict[str, str]
) -> None:
    article = await make_article(client)
    if fields["body"]:
        await edit(client, article["id"], 1, **fields)
        expected = 2
    else:
        expected = 1
    response = await publish(client, article["id"], expected)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_content"
    assert await snapshots(engine, article["id"]) == []
    detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    assert detail["status"] == "draft"
    assert detail["draft_version"] == expected
    assert detail["published_at"] is None


async def test_a_stale_version_returns_409_and_creates_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await make_article(client, body="Text")
    response = await publish(client, article["id"], 5)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "version_conflict"
    assert error["details"] == {"current_draft_version": 1}
    assert await snapshots(engine, article["id"]) == []


async def test_the_version_check_comes_before_the_empty_check(
    client: httpx.AsyncClient,
) -> None:
    article = await make_article(client)  # empty body, and a stale version
    response = await publish(client, article["id"], 9)
    assert response.status_code == 409


async def test_a_missing_article_returns_404(client: httpx.AsyncClient) -> None:
    assert (await publish(client, 999999, 1)).status_code == 404
    bad_body = await client.post("/api/v1/articles/999999/publish", json={})
    assert bad_body.status_code == 404  # 404 comes before 422


async def test_the_expected_version_is_required(client: httpx.AsyncClient) -> None:
    article = await make_article(client, body="Text")
    response = await client.post(f"/api/v1/articles/{article['id']}/publish", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_no_credentials_returns_401_first(secured_client: httpx.AsyncClient) -> None:
    response = await publish(secured_client, 999999, 1)
    assert response.status_code == 401
