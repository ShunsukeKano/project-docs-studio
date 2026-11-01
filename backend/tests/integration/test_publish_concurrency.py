"""Racing publishes with one expected version: exactly one wins, the rest get 409."""

import asyncio

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_articles_create_edit_list import make_article
from tests.integration.test_publish_lifecycle import publish


@pytest.mark.parametrize("racers", [2, 5])
async def test_exactly_one_publish_wins(
    client: httpx.AsyncClient, engine: AsyncEngine, racers: int
) -> None:
    article = await make_article(client, body="Text")
    responses = await asyncio.gather(*(publish(client, article["id"], 1) for _ in range(racers)))

    codes = sorted(r.status_code for r in responses)
    assert codes == [201] + [409] * (racers - 1), [r.text for r in responses]
    assert all(r.status_code < 500 for r in responses)

    async with engine.connect() as conn:
        numbers = [
            row[0]
            for row in await conn.execute(
                text(
                    "SELECT version_number FROM article_versions WHERE article_id=:a "
                    "ORDER BY version_number"
                ),
                {"a": article["id"]},
            )
        ]
        live = (
            await conn.execute(
                text(
                    "SELECT v.version_number FROM articles a "
                    "JOIN article_versions v ON v.id = a.current_published_version_id "
                    "WHERE a.id = :a"
                ),
                {"a": article["id"]},
            )
        ).scalar_one()
    assert numbers == [1]
    assert live == max(numbers)


async def test_a_chain_of_racing_publishes_keeps_numbers_contiguous(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await make_article(client, body="Text")
    expected = 1
    for round_number in range(1, 4):
        results = await asyncio.gather(
            *(publish(client, article["id"], expected) for _ in range(3))
        )
        winners = [r for r in results if r.status_code == 201]
        assert len(winners) == 1
        assert winners[0].json()["version_number"] == round_number
        expected = winners[0].json()["draft_version"]
        edit = await client.patch(
            f"/api/v1/articles/{article['id']}",
            json={"expected_draft_version": expected, "body": f"Round {round_number}"},
        )
        expected = edit.json()["draft_version"]
    async with engine.connect() as conn:
        numbers = [
            row[0]
            for row in await conn.execute(
                text(
                    "SELECT version_number FROM article_versions WHERE article_id=:a "
                    "ORDER BY version_number"
                ),
                {"a": article["id"]},
            )
        ]
    assert numbers == [1, 2, 3]
