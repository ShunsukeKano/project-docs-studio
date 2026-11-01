"""With authentication on, every writer route needs the right credentials (US8, FR-028 to 031)."""

import base64
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.db.session import create_session_factory
from app.main import create_app
from tests.api.test_check_order import MISSING, ROUTES
from tests.conftest import TEST_WRITER_PASSWORD, TEST_WRITER_USER

RIGHT = httpx.BasicAuth(TEST_WRITER_USER, TEST_WRITER_PASSWORD)
WRONG_PASSWORD = httpx.BasicAuth(TEST_WRITER_USER, "not-the-password")
WRONG_USER = httpx.BasicAuth("somebody-else", TEST_WRITER_PASSWORD)
LIST_AND_CREATE = [
    ("GET", "/api/v1/articles", None),
    ("POST", "/api/v1/articles", {"title": "T", "slug": "t"}),
]
ALL_ROUTES = [(m, t.format(id=MISSING), b) for m, t, b in ROUTES] + LIST_AND_CREATE


def basic_header(raw: bytes) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


@pytest.mark.parametrize(("method", "path", "body"), ALL_ROUTES)
@pytest.mark.parametrize("auth", [None, WRONG_PASSWORD, WRONG_USER], ids=["none", "pass", "user"])
async def test_missing_or_wrong_credentials_get_401_even_for_a_missing_article(
    secured_client: httpx.AsyncClient, method: str, path: str, body: Any, auth: Any
) -> None:
    response = await secured_client.request(method, path, json=body, auth=auth)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("method", "path", "body"), ALL_ROUTES)
async def test_right_credentials_reach_the_route(
    secured_client: httpx.AsyncClient, method: str, path: str, body: Any
) -> None:
    response = await secured_client.request(method, path, json=body, auth=RIGHT)
    assert response.status_code in (200, 201, 404)  # the route ran, so never 401
    assert response.headers["cache-control"] == "no-store"


async def test_a_successful_writer_response_is_not_stored(
    secured_client: httpx.AsyncClient,
) -> None:
    response = await secured_client.get("/api/v1/articles", auth=RIGHT)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "header",
    [
        "Basic",
        "Basic ",
        "Basic !!!not-base64!!!",
        "Bearer abc",
        "basic " + base64.b64encode(b"no-colon").decode(),
        "Digest username=x",
        "",
    ],
)
async def test_malformed_headers_get_401_not_a_500(
    secured_client: httpx.AsyncClient, header: str
) -> None:
    response = await secured_client.get("/api/v1/articles", headers={"Authorization": header})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "raw",
    [
        "\u30e9\u30a4\u30bf\u30fc:\u30d1\u30b9\u30ef\u30fc\u30c9".encode(),
        b"\xff\xfe:\xff",  # not valid UTF-8 at all
        "\u00e9:\u00e9".encode("latin-1"),
        b":",
    ],
)
async def test_non_ascii_credentials_never_cause_a_500(
    secured_client: httpx.AsyncClient, raw: bytes
) -> None:
    response = await secured_client.get("/api/v1/articles", headers=basic_header(raw))
    assert response.status_code == 401


async def test_non_ascii_credentials_work_when_they_are_the_configured_ones(
    engine: AsyncEngine,
) -> None:
    settings = Settings(
        env="local",
        basic_auth_enabled=True,
        basic_auth_user="\u30e9\u30a4\u30bf\u30fc",
        basic_auth_password="\u30d1\u30b9\u30ef\u30fc\u30c9\U0001f511",
    )
    app = create_app(settings)
    app.state.session_factory = create_session_factory(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        good = await http.get(
            "/api/v1/articles",
            auth=httpx.BasicAuth(
                "\u30e9\u30a4\u30bf\u30fc", "\u30d1\u30b9\u30ef\u30fc\u30c9\U0001f511"
            ),
        )
        bad = await http.get(
            "/api/v1/articles",
            auth=httpx.BasicAuth("\u30e9\u30a4\u30bf\u30fc", "\u30d1\u30b9\u30ef\u30fc\u30c9"),
        )
    assert good.status_code == 200
    assert bad.status_code == 401


async def test_a_password_that_only_starts_the_same_is_refused(
    secured_client: httpx.AsyncClient,
) -> None:
    for password in (TEST_WRITER_PASSWORD[:-1], TEST_WRITER_PASSWORD + "x", ""):
        auth = httpx.BasicAuth(TEST_WRITER_USER, password)
        assert (await secured_client.get("/api/v1/articles", auth=auth)).status_code == 401


async def test_a_public_route_with_a_stray_authorization_header_still_works(
    secured_client: httpx.AsyncClient,
) -> None:
    headers = basic_header(b"someone:else")
    assert (await secured_client.get("/api/v1/public/articles", headers=headers)).status_code == 200
    assert (await secured_client.get("/healthz", headers=headers)).status_code == 200


async def test_the_liveness_check_needs_no_credentials(secured_client: httpx.AsyncClient) -> None:
    response = await secured_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_stray_whitespace_in_the_configured_login_does_not_lock_the_writer_out(
    engine: AsyncEngine,
) -> None:
    # A secret saved through a console or a script often carries a trailing newline or spaces.
    settings = Settings(
        env="local",
        basic_auth_enabled=True,
        basic_auth_user="writer\n",
        basic_auth_password="  local-test-only \r\n",
    )
    app = create_app(settings)
    app.state.session_factory = create_session_factory(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        clean = await http.get(
            "/api/v1/articles", auth=httpx.BasicAuth("writer", "local-test-only")
        )
        wrong = await http.get("/api/v1/articles", auth=httpx.BasicAuth("writer", "other"))
    assert clean.status_code == 200
    assert wrong.status_code == 401


def test_a_login_that_is_only_whitespace_counts_as_empty() -> None:
    with pytest.raises(ValueError, match="must both be set"):
        Settings(
            env="local",
            basic_auth_enabled=True,
            basic_auth_user=" \n",
            basic_auth_password="x",
        )
