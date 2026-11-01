"""draft_version moves only on edit, Restore and a snapshot-creating Publish (US6, FR-019).

A publish that creates nothing is covered by test_idempotent_publish.py (US7).
"""

import httpx

from tests.api.test_articles_create_edit_list import make_article
from tests.api.test_versions_history import build_versions, versions_path
from tests.integration.test_delete_version import delete
from tests.integration.test_publish_lifecycle import edit, publish
from tests.integration.test_restore import restore
from tests.integration.test_unpublish import unpublish


async def draft_version(client: httpx.AsyncClient, article_id: int) -> int:
    return int((await client.get(f"/api/v1/articles/{article_id}")).json()["draft_version"])


async def test_a_new_article_starts_at_1(client: httpx.AsyncClient) -> None:
    assert (await make_article(client))["draft_version"] == 1


async def test_each_successful_edit_adds_exactly_1(client: httpx.AsyncClient) -> None:
    article = await make_article(client)
    for expected in (1, 2, 3):
        assert (await edit(client, article["id"], expected, title=f"T{expected}"))[
            "draft_version"
        ] == expected + 1


async def test_a_snapshot_creating_publish_adds_exactly_1(client: httpx.AsyncClient) -> None:
    article = await make_article(client, body="Text")
    assert (await publish(client, article["id"], 1)).json()["draft_version"] == 2
    assert await draft_version(client, article["id"]) == 2


async def test_restore_adds_exactly_1(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "restore-bump", 2)
    before = await draft_version(client, article["id"])
    assert (await restore(client, article["id"], 1, before)).json()["draft_version"] == before + 1


async def test_unpublish_and_delete_do_not_change_it(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "no-bump", 2)
    before = await draft_version(client, article["id"])

    assert (await delete(client, article["id"], 1)).status_code == 204
    assert await draft_version(client, article["id"]) == before

    assert (await unpublish(client, article["id"])).status_code == 200
    assert await draft_version(client, article["id"]) == before


async def test_a_refused_request_does_not_change_it(client: httpx.AsyncClient) -> None:
    article = await build_versions(client, "refused", 2)
    before = await draft_version(client, article["id"])
    await edit_stale(client, article["id"], before - 1)
    await delete(client, article["id"], 2)  # the live one: refused
    await client.get(versions_path(article["id"]))
    assert await draft_version(client, article["id"]) == before


async def edit_stale(client: httpx.AsyncClient, article_id: int, expected: int) -> None:
    response = await client.patch(
        f"/api/v1/articles/{article_id}", json={"expected_draft_version": expected, "body": "x"}
    )
    assert response.status_code == 409
