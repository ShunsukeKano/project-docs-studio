"""Version history: list, open one, and the 404 rules (US5)."""

from typing import Any

import httpx
import pytest

from tests.api.test_articles_create_edit_list import make_article
from tests.integration.test_publish_lifecycle import edit, publish


async def build_versions(client: httpx.AsyncClient, slug: str, count: int) -> dict[str, Any]:
    """Publish `count` snapshots titled "Title 1", "Title 2", ... and return the article."""
    article = await make_article(client, slug, title="Title 1", body="Body 1", tags=["t1"])
    draft_version = 1
    for number in range(1, count + 1):
        if number > 1:
            updated = await edit(
                client,
                article["id"],
                draft_version,
                title=f"Title {number}",
                body=f"Body {number}",
                tags=[f"t{number}"],
            )
            draft_version = updated["draft_version"]
        response = await publish(client, article["id"], draft_version)
        assert response.status_code == 201, response.text
        draft_version = response.json()["draft_version"]
    return article


def versions_path(article_id: int, number: int | None = None) -> str:
    base = f"/api/v1/articles/{article_id}/versions"
    return base if number is None else f"{base}/{number}"


async def test_the_history_is_newest_first_without_the_body(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "history", 3)
    response = await client.get(versions_path(article["id"]))
    assert response.status_code == 200
    items = response.json()
    assert [i["version_number"] for i in items] == [3, 2, 1]
    assert [i["title"] for i in items] == ["Title 3", "Title 2", "Title 1"]
    assert [i["is_live"] for i in items] == [True, False, False]
    for item in items:
        assert set(item) == {"id", "version_number", "title", "created_at", "is_live"}


async def test_a_never_published_article_has_an_empty_history(client: httpx.AsyncClient) -> None:
    article = await make_article(client)
    assert (await client.get(versions_path(article["id"]))).json() == []


async def test_the_live_flag_stays_after_unpublish(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "still-live", 2)
    await client.post(f"/api/v1/articles/{article['id']}/unpublish")
    items = (await client.get(versions_path(article["id"]))).json()
    assert [i["is_live"] for i in items] == [True, False]


async def test_opening_a_version_shows_the_full_content(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "open-one", 2)
    response = await client.get(versions_path(article["id"], 1))
    assert response.status_code == 200
    version = response.json()
    assert version["version_number"] == 1
    assert version["title"] == "Title 1"
    assert version["body"] == "Body 1"
    assert version["tags"] == ["t1"]
    assert version["is_live"] is False
    assert (await client.get(versions_path(article["id"], 2))).json()["is_live"] is True


async def test_a_number_the_article_does_not_have_returns_404(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "no-such-number", 1)
    response = await client.get(versions_path(article["id"], 99))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_another_articles_version_is_not_reachable(client: httpx.AsyncClient) -> None:
    first = await build_versions(client, "first-article", 2)
    second = await build_versions(client, "second-article", 1)
    assert (await client.get(versions_path(second["id"], 2))).status_code == 404
    assert (await client.get(versions_path(first["id"], 2))).status_code == 200


async def test_a_missing_article_returns_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(versions_path(999999))).status_code == 404
    assert (await client.get(versions_path(999999, 1))).status_code == 404


async def test_a_version_number_below_1_returns_422(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "zero", 1)
    assert (await client.get(versions_path(article["id"], 0))).status_code == 422


@pytest.mark.parametrize("number", [None, 1])
async def test_no_credentials_returns_401_first(
    secured_client: httpx.AsyncClient, number: int | None
) -> None:
    assert (await secured_client.get(versions_path(999999, number))).status_code == 401
