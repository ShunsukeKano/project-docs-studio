"""Create, edit and list drafts through the HTTP API (User Story 1)."""

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import TEST_WRITER_PASSWORD, TEST_WRITER_USER

AUTH = httpx.BasicAuth(TEST_WRITER_USER, TEST_WRITER_PASSWORD)


async def make_article(
    client: httpx.AsyncClient, slug: str = "intro", **fields: object
) -> dict[str, Any]:
    payload = {"title": "Intro", "slug": slug, **fields}
    response = await client.post("/api/v1/articles", json=payload)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


class TestCreate:
    async def test_returns_201_with_location_and_a_new_draft(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/articles",
            json={"title": "Hello", "slug": "hello", "body": "Text", "tags": ["a"]},
        )
        assert response.status_code == 201
        article = response.json()
        assert response.headers["location"] == f"/api/v1/articles/{article['id']}"
        assert article["status"] == "draft"
        assert article["draft_version"] == 1
        assert article["slug"] == "hello"
        assert article["draft_title"] == "Hello"
        assert article["draft_body"] == "Text"
        assert article["draft_tags"] == ["a"]
        assert article["published_at"] is None
        assert article["live_version_number"] is None

    async def test_creates_no_snapshot(
        self, client: httpx.AsyncClient, engine: AsyncEngine
    ) -> None:
        await make_article(client)
        async with engine.connect() as conn:
            count = (await conn.execute(text("SELECT count(*) FROM article_versions"))).scalar_one()
        assert count == 0

    async def test_the_response_has_the_no_store_header(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/v1/articles", json={"title": "T", "slug": "t"})
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.parametrize(
        "payload",
        [
            {"slug": "no-title"},
            {"title": "No slug"},
            {"title": " ", "slug": "blank-title"},
            {"title": "T", "slug": "Bad Slug"},
            {"title": "T", "slug": "ok", "tags": ["x"] * 11},
            {"title": "T", "slug": "ok", "unknown": 1},
        ],
    )
    async def test_invalid_input_returns_422_and_changes_nothing(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> None:
        response = await client.post("/api/v1/articles", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        listing = await client.get("/api/v1/articles")
        assert listing.json() == []


class TestEdit:
    async def test_a_successful_edit_raises_the_draft_version_by_one(
        self, client: httpx.AsyncClient
    ) -> None:
        article = await make_article(client)
        response = await client.patch(
            f"/api/v1/articles/{article['id']}",
            json={"expected_draft_version": 1, "title": "Changed"},
        )
        assert response.status_code == 200
        assert response.json()["draft_version"] == 2
        assert response.json()["draft_title"] == "Changed"

    async def test_is_partial_and_tags_replace_the_whole_list(
        self, client: httpx.AsyncClient
    ) -> None:
        article = await make_article(client, body="Keep me", tags=["one", "two"])
        response = await client.patch(
            f"/api/v1/articles/{article['id']}",
            json={"expected_draft_version": 1, "tags": ["three"]},
        )
        updated = response.json()
        assert updated["draft_title"] == "Intro"
        assert updated["draft_body"] == "Keep me"
        assert updated["draft_tags"] == ["three"]

    async def test_a_body_can_be_cleared_to_empty(self, client: httpx.AsyncClient) -> None:
        article = await make_article(client, body="Text")
        response = await client.patch(
            f"/api/v1/articles/{article['id']}", json={"expected_draft_version": 1, "body": ""}
        )
        assert response.json()["draft_body"] == ""

    async def test_the_slug_cannot_be_sent(self, client: httpx.AsyncClient) -> None:
        article = await make_article(client)
        response = await client.patch(
            f"/api/v1/articles/{article['id']}",
            json={"expected_draft_version": 1, "slug": "new-slug"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        after = await client.get(f"/api/v1/articles/{article['id']}")
        assert after.json()["slug"] == "intro"
        assert after.json()["draft_version"] == 1

    async def test_needs_the_expected_draft_version(self, client: httpx.AsyncClient) -> None:
        article = await make_article(client)
        response = await client.patch(f"/api/v1/articles/{article['id']}", json={"title": "X"})
        assert response.status_code == 422

    async def test_a_stale_version_returns_409_with_the_current_version(
        self, client: httpx.AsyncClient
    ) -> None:
        article = await make_article(client)
        path = f"/api/v1/articles/{article['id']}"
        await client.patch(path, json={"expected_draft_version": 1, "title": "First"})
        stale = await client.patch(path, json={"expected_draft_version": 1, "title": "Second"})
        assert stale.status_code == 409
        error = stale.json()["error"]
        assert error["code"] == "version_conflict"
        assert error["details"] == {"current_draft_version": 2}
        assert (await client.get(path)).json()["draft_title"] == "First"

    async def test_validation_comes_before_the_version_check(
        self, client: httpx.AsyncClient
    ) -> None:
        article = await make_article(client)
        response = await client.patch(
            f"/api/v1/articles/{article['id']}",
            json={"expected_draft_version": 99, "title": "  "},
        )
        assert response.status_code == 422

    async def test_a_missing_article_returns_404(self, client: httpx.AsyncClient) -> None:
        response = await client.patch(
            "/api/v1/articles/999999", json={"expected_draft_version": 1, "title": "X"}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    async def test_not_found_comes_before_validation(self, client: httpx.AsyncClient) -> None:
        response = await client.patch("/api/v1/articles/999999", json={"title": " "})
        assert response.status_code == 404

    async def test_get_returns_the_article_or_404(self, client: httpx.AsyncClient) -> None:
        article = await make_article(client)
        assert (await client.get(f"/api/v1/articles/{article['id']}")).json() == article
        assert (await client.get("/api/v1/articles/999999")).status_code == 404


class TestList:
    async def test_newest_change_first_with_ties_by_id_descending(
        self, client: httpx.AsyncClient
    ) -> None:
        first = await make_article(client, "first")
        second = await make_article(client, "second")
        third = await make_article(client, "third")
        # Editing the first one makes it the most recently changed.
        await client.patch(
            f"/api/v1/articles/{first['id']}", json={"expected_draft_version": 1, "title": "New"}
        )
        slugs = [a["slug"] for a in (await client.get("/api/v1/articles")).json()]
        assert slugs == ["first", "third", "second"]
        assert second["id"] < third["id"]

    async def test_each_item_has_the_summary_fields(self, client: httpx.AsyncClient) -> None:
        article = await make_article(client)
        item = (await client.get("/api/v1/articles")).json()[0]
        assert set(item) == {"id", "slug", "status", "title", "draft_version", "updated_at"}
        assert item["id"] == article["id"]
        assert item["title"] == "Intro"
        assert item["status"] == "draft"

    async def test_limit_offset_and_the_cap_of_100(self, client: httpx.AsyncClient) -> None:
        for number in range(3):
            await make_article(client, f"a{number}")
        page = await client.get("/api/v1/articles", params={"limit": 2, "offset": 1})
        assert [a["slug"] for a in page.json()] == ["a1", "a0"]
        assert (await client.get("/api/v1/articles", params={"limit": 101})).status_code == 422
        assert (await client.get("/api/v1/articles", params={"limit": 0})).status_code == 422
        assert (await client.get("/api/v1/articles", params={"offset": -1})).status_code == 422

    async def test_can_be_filtered_by_status(self, client: httpx.AsyncClient) -> None:
        await make_article(client)
        drafts = await client.get("/api/v1/articles", params={"status": "draft"})
        assert len(drafts.json()) == 1
        published = await client.get("/api/v1/articles", params={"status": "published"})
        assert published.json() == []

    async def test_an_unknown_status_returns_422(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/articles", params={"status": "archived"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


class TestAuthenticationComesFirst:
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("POST", "/api/v1/articles", {"bad": "body"}),
            ("GET", "/api/v1/articles?status=nonsense", None),
            ("GET", "/api/v1/articles/999999", None),
            ("PATCH", "/api/v1/articles/999999", {"bad": "body"}),
        ],
    )
    async def test_no_credentials_returns_401_before_404_or_422(
        self, secured_client: httpx.AsyncClient, method: str, path: str, body: dict[str, Any] | None
    ) -> None:
        response = await secured_client.request(method, path, json=body)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert response.headers["www-authenticate"] == 'Basic realm="studio"'

    async def test_wrong_credentials_return_401(self, secured_client: httpx.AsyncClient) -> None:
        response = await secured_client.get(
            "/api/v1/articles", auth=httpx.BasicAuth(TEST_WRITER_USER, "wrong")
        )
        assert response.status_code == 401

    async def test_right_credentials_get_through(self, secured_client: httpx.AsyncClient) -> None:
        response = await secured_client.get("/api/v1/articles", auth=AUTH)
        assert response.status_code == 200
        created = await secured_client.post(
            "/api/v1/articles", json={"title": "T", "slug": "t"}, auth=AUTH
        )
        assert created.status_code == 201
