"""Delete racing Publish never gives a 5xx and never leaves the live pointer dangling (US5)."""

import asyncio

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_versions_history import build_versions
from tests.integration.test_delete_version import delete
from tests.integration.test_publish_lifecycle import edit, publish


@pytest.mark.parametrize("target", [1, 2])
@pytest.mark.parametrize("round_number", range(4))
async def test_no_5xx_and_the_pointer_always_points_at_a_real_snapshot(
    client: httpx.AsyncClient, engine: AsyncEngine, target: int, round_number: int
) -> None:
    article = await build_versions(client, "delete-race", 2)  # v2 is live
    detail = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    updated = await edit(client, article["id"], detail["draft_version"], body="Third")

    publish_response, delete_response = await asyncio.gather(
        publish(client, article["id"], updated["draft_version"]),
        delete(client, article["id"], target),
    )

    assert publish_response.status_code == 201
    if target == 1:
        assert delete_response.status_code == 204  # never protected
    else:
        # Deleting v2 wins only if it runs after the publish moved the pointer to v3.
        assert delete_response.status_code in (204, 409)
    async with engine.connect() as conn:
        live = (
            await conn.execute(
                text(
                    "SELECT v.version_number FROM articles a JOIN article_versions v "
                    "ON v.id = a.current_published_version_id WHERE a.id = :a"
                ),
                {"a": article["id"]},
            )
        ).scalar_one()
    assert live == 3
