"""Public responses carry an allow-list of fields and nothing else (FR-025)."""

import httpx
import pytest

from tests.api.test_public_read import PUBLIC, publish_new
from tests.conftest import TEST_WRITER_PASSWORD, TEST_WRITER_USER

LIST_FIELDS = {"slug", "title", "tags", "published_at", "updated_at"}
DETAIL_FIELDS = {"slug", "title", "tags", "body", "published_at", "live_created_at"}
FORBIDDEN = ("draft", "status", "id", "version", "created_at")


async def test_the_list_has_only_the_allowed_fields(client: httpx.AsyncClient) -> None:
    await publish_new(client, "one")
    item = (await client.get(PUBLIC)).json()[0]
    assert set(item) == LIST_FIELDS


async def test_the_detail_has_only_the_allowed_fields(client: httpx.AsyncClient) -> None:
    await publish_new(client, "one")
    page = (await client.get(f"{PUBLIC}/one")).json()
    assert set(page) == DETAIL_FIELDS


async def test_no_internal_or_draft_field_leaks_anywhere(client: httpx.AsyncClient) -> None:
    await publish_new(client, "one")
    bodies = [(await client.get(PUBLIC)).text, (await client.get(f"{PUBLIC}/one")).text]
    for body in bodies:
        for word in FORBIDDEN:
            assert f'"{word}' not in body.replace("published_at", "").replace("live_created_at", "")


@pytest.mark.parametrize("path", [PUBLIC, f"{PUBLIC}/one"])
async def test_no_long_lived_cache_header_is_sent(client: httpx.AsyncClient, path: str) -> None:
    await publish_new(client, "one")
    header = (await client.get(path)).headers.get("cache-control", "")
    assert "max-age" not in header
    assert "public" not in header
    assert "s-maxage" not in header


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic Zm9vOmJhcg=="},
        {"Authorization": "Bearer nonsense"},
    ],
)
async def test_public_routes_accept_requests_with_and_without_an_authorization_header(
    secured_client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    assert (await secured_client.get(PUBLIC, headers=headers)).status_code == 200


async def test_valid_writer_credentials_are_not_required_but_harmless(
    secured_client: httpx.AsyncClient,
) -> None:
    auth = httpx.BasicAuth(TEST_WRITER_USER, TEST_WRITER_PASSWORD)
    assert (await secured_client.get(PUBLIC, auth=auth)).status_code == 200
