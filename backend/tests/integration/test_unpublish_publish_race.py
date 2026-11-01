"""Unpublish and Publish at the same moment serialize on the row lock (US4)."""

import asyncio

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_public_read import publish_new
from tests.integration.test_publish_lifecycle import edit, publish
from tests.integration.test_unpublish import unpublish


@pytest.mark.parametrize("round_number", range(5))
async def test_either_order_leaves_a_valid_state_and_no_5xx(
    client: httpx.AsyncClient, engine: AsyncEngine, round_number: int
) -> None:
    article = await publish_new(client, "race", body="One")
    await edit(client, article["id"], 2, body="Two")  # draft_version 3, so a publish is possible

    publish_response, unpublish_response = await asyncio.gather(
        publish(client, article["id"], 3), unpublish(client, article["id"])
    )

    assert publish_response.status_code == 201
    assert unpublish_response.status_code == 200
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT a.status, v.version_number, a.last_version_number "
                    "FROM articles a JOIN article_versions v "
                    "  ON v.id = a.current_published_version_id WHERE a.id = :a"
                ),
                {"a": article["id"]},
            )
        ).one()
    # Publish-then-unpublish ends "unpublished"; unpublish-then-publish ends "published".
    # Both are valid, and the pointer is on the newest snapshot either way.
    assert row.status in ("published", "unpublished")
    assert row.version_number == row.last_version_number == 2
