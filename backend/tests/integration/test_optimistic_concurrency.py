"""Optimistic concurrency: a change based on a stale draft is refused and changes nothing (US6)."""

import asyncio

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_versions_history import build_versions
from tests.integration.test_publish_lifecycle import edit, publish, snapshots
from tests.integration.test_restore import restore


async def test_a_stale_edit_returns_409_and_does_not_overwrite_the_newer_edit(
    client: httpx.AsyncClient,
) -> None:
    article = await build_versions(client, "two-tabs", 1)
    path = f"/api/v1/articles/{article['id']}"
    view = (await client.get(path)).json()  # both writers open the same draft_version
    first = await client.patch(
        path, json={"expected_draft_version": view["draft_version"], "body": "Writer one"}
    )
    second = await client.patch(
        path, json={"expected_draft_version": view["draft_version"], "body": "Writer two"}
    )

    assert first.status_code == 200
    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "version_conflict"
    assert error["details"] == {"current_draft_version": first.json()["draft_version"]}
    assert (await client.get(path)).json()["draft_body"] == "Writer one"


async def test_an_edit_and_a_restore_with_the_same_version_give_exactly_one_success(
    client: httpx.AsyncClient,
) -> None:
    for round_number in range(5):
        article = await build_versions(client, f"edit-vs-restore-{round_number}", 2)
        view = (await client.get(f"/api/v1/articles/{article['id']}")).json()
        expected = view["draft_version"]

        edit_response, restore_response = await asyncio.gather(
            client.patch(
                f"/api/v1/articles/{article['id']}",
                json={"expected_draft_version": expected, "body": "Edited"},
            ),
            restore(client, article["id"], 1, expected),
        )

        assert sorted([edit_response.status_code, restore_response.status_code]) == [200, 409]
        final = (await client.get(f"/api/v1/articles/{article['id']}")).json()
        assert final["draft_version"] == expected + 1


async def test_a_publish_older_than_a_committed_edit_returns_409_and_creates_no_snapshot(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    article = await build_versions(client, "stale-publish", 1)
    view = (await client.get(f"/api/v1/articles/{article['id']}")).json()
    await edit(client, article["id"], view["draft_version"], body="Changed after I looked")

    response = await publish(client, article["id"], view["draft_version"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    assert response.json()["error"]["details"] == {
        "current_draft_version": view["draft_version"] + 1
    }
    assert [s[0] for s in await snapshots(engine, article["id"])] == [1]
