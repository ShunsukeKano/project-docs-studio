"""A taken slug gets the smallest free numeric suffix, even when creates race."""

import asyncio

import httpx

from tests.api.test_articles_create_edit_list import make_article


async def create(client: httpx.AsyncClient, slug: str) -> httpx.Response:
    return await client.post("/api/v1/articles", json={"title": "T", "slug": slug})


async def test_a_taken_slug_gets_2_then_3(client: httpx.AsyncClient) -> None:
    assert (await make_article(client, "guide"))["slug"] == "guide"
    assert (await make_article(client, "guide"))["slug"] == "guide-2"
    assert (await make_article(client, "guide"))["slug"] == "guide-3"


async def test_the_smallest_free_number_is_used(client: httpx.AsyncClient) -> None:
    await make_article(client, "guide")
    await make_article(client, "guide-2")
    await make_article(client, "guide-3")
    # Asking for a number that is already taken moves on to the next free one.
    assert (await make_article(client, "guide-2"))["slug"] == "guide-2-2"
    assert (await make_article(client, "guide"))["slug"] == "guide-4"


async def test_the_base_is_shortened_to_stay_within_100_characters(
    client: httpx.AsyncClient,
) -> None:
    base = "a" * 100
    assert (await make_article(client, base))["slug"] == base
    second = (await make_article(client, base))["slug"]
    assert second == "a" * 98 + "-2"
    assert len(second) == 100
    assert (await make_article(client, base))["slug"] == "a" * 98 + "-3"


async def test_shortening_never_leaves_a_trailing_hyphen(client: httpx.AsyncClient) -> None:
    base = "a" * 97 + "-bb"  # 100 characters; cutting to 98 would end in a hyphen
    await make_article(client, base)
    second = (await make_article(client, base))["slug"]
    assert second == "a" * 97 + "-2"


async def test_concurrent_creates_get_different_slugs_and_never_a_500(
    client: httpx.AsyncClient,
) -> None:
    await make_article(client, "race")
    responses = await asyncio.gather(*(create(client, "race") for _ in range(4)))
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    slugs = {r.json()["slug"] for r in responses}
    assert len(slugs) == 4
    assert slugs == {"race-2", "race-3", "race-4", "race-5"}


async def test_the_slug_cannot_change_afterwards(client: httpx.AsyncClient) -> None:
    article = await make_article(client, "stable")
    response = await client.patch(
        f"/api/v1/articles/{article['id']}", json={"expected_draft_version": 1, "slug": "other"}
    )
    assert response.status_code == 422
    assert (await client.get(f"/api/v1/articles/{article['id']}")).json()["slug"] == "stable"
