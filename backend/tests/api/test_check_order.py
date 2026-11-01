"""The order of checks is the same on every writer route (FR-033):

authentication (401), existence (404), input shape (422), expected_draft_version (409),
then business rules (empty_content, not_published, version_is_live).
"""

from typing import Any

import httpx
import pytest

from tests.api.test_articles_create_edit_list import make_article
from tests.api.test_versions_history import build_versions
from tests.conftest import TEST_WRITER_PASSWORD, TEST_WRITER_USER

MISSING = 999999
BAD_BODY: dict[str, Any] = {"expected_draft_version": 0}  # fails the shape check

# (method, path template, valid body or None) for every writer route that has an article id.
ROUTES = [
    ("GET", "/api/v1/articles/{id}", None),
    ("PATCH", "/api/v1/articles/{id}", {"expected_draft_version": 1, "title": "T"}),
    ("POST", "/api/v1/articles/{id}/publish", {"expected_draft_version": 1}),
    ("POST", "/api/v1/articles/{id}/unpublish", None),
    ("GET", "/api/v1/articles/{id}/versions", None),
    ("GET", "/api/v1/articles/{id}/versions/1", None),
    ("DELETE", "/api/v1/articles/{id}/versions/1", None),
    ("POST", "/api/v1/articles/{id}/versions/1/restore", {"expected_draft_version": 1}),
]
WITH_BODY = [r for r in ROUTES if r[2] is not None and r[0] != "GET"]


@pytest.mark.parametrize(("method", "template", "body"), ROUTES)
async def test_401_comes_before_404(
    secured_client: httpx.AsyncClient, method: str, template: str, body: Any
) -> None:
    response = await secured_client.request(method, template.format(id=MISSING), json=body)
    assert response.status_code == 401


@pytest.mark.parametrize(("method", "template", "body"), ROUTES)
async def test_404_for_a_missing_article_with_valid_input(
    client: httpx.AsyncClient, method: str, template: str, body: Any
) -> None:
    response = await client.request(method, template.format(id=MISSING), json=body)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(("method", "template", "_"), WITH_BODY)
async def test_404_comes_before_422(
    client: httpx.AsyncClient, method: str, template: str, _: Any
) -> None:
    response = await client.request(method, template.format(id=MISSING), json=BAD_BODY)
    assert response.status_code == 404


@pytest.mark.parametrize(("method", "template", "_"), WITH_BODY)
async def test_422_comes_before_409(
    client: httpx.AsyncClient, method: str, template: str, _: Any
) -> None:
    article = await build_versions(client, "shape-first", 2)  # draft_version is 3, not 0
    response = await client.request(
        method,
        template.format(id=article["id"]),
        json={**BAD_BODY, "title": "T"} if method == "PATCH" else BAD_BODY,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_409_comes_before_the_business_rules_of_publish(client: httpx.AsyncClient) -> None:
    article = await make_article(client)  # an empty body: empty_content if the version matched
    stale = await client.post(
        f"/api/v1/articles/{article['id']}/publish", json={"expected_draft_version": 7}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
    fresh = await client.post(
        f"/api/v1/articles/{article['id']}/publish", json={"expected_draft_version": 1}
    )
    assert fresh.status_code == 422
    assert fresh.json()["error"]["code"] == "empty_content"


async def test_422_shape_comes_before_empty_content(client: httpx.AsyncClient) -> None:
    article = await make_article(client)  # empty body
    response = await client.post(
        f"/api/v1/articles/{article['id']}/publish", json={"expected_draft_version": 0}
    )
    assert response.json()["error"]["code"] == "validation_error"


async def test_the_conflict_has_the_same_details_on_every_route(
    client: httpx.AsyncClient,
) -> None:
    article = await build_versions(client, "same-details", 2)
    current = (await client.get(f"/api/v1/articles/{article['id']}")).json()["draft_version"]
    stale = current - 1
    id_ = article["id"]
    responses = [
        await client.patch(
            f"/api/v1/articles/{id_}", json={"expected_draft_version": stale, "title": "T"}
        ),
        await client.post(
            f"/api/v1/articles/{id_}/publish", json={"expected_draft_version": stale}
        ),
        await client.post(
            f"/api/v1/articles/{id_}/versions/1/restore", json={"expected_draft_version": stale}
        ),
    ]
    assert [r.status_code for r in responses] == [409, 409, 409]
    for response in responses:
        assert response.json()["error"]["code"] == "version_conflict"
        assert response.json()["error"]["details"] == {"current_draft_version": current}


async def test_unpublish_and_delete_need_no_version_and_apply_business_rules(
    client: httpx.AsyncClient,
) -> None:
    article = await make_article(client)
    unpublish = await client.post(f"/api/v1/articles/{article['id']}/unpublish")
    assert unpublish.status_code == 409
    assert unpublish.json()["error"]["code"] == "not_published"

    live = await build_versions(client, "live-rule", 1)
    refused = await client.delete(f"/api/v1/articles/{live['id']}/versions/1")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "version_is_live"


async def test_right_credentials_reach_the_route(secured_client: httpx.AsyncClient) -> None:
    auth = httpx.BasicAuth(TEST_WRITER_USER, TEST_WRITER_PASSWORD)
    response = await secured_client.get(f"/api/v1/articles/{MISSING}", auth=auth)
    assert response.status_code == 404
