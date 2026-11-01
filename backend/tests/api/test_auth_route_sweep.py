"""Every route outside the public area must answer 401 without credentials."""

import httpx
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.core.config import Settings
from app.main import create_app

OPEN_PREFIXES = ("/api/v1/public",)
OPEN_PATHS = {"/healthz"}
DOC_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


def _is_open(path: str) -> bool:
    return path in OPEN_PATHS or path in DOC_PATHS or path.startswith(OPEN_PREFIXES)


async def unprotected_routes(app: FastAPI) -> list[str]:
    """Routes that answered something other than 401 when called with no credentials."""
    failures: list[str] = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for route in app.routes:
            if not isinstance(route, APIRoute) or _is_open(route.path):
                continue
            path = route.path
            for name in route.param_convertors:
                path = path.replace("{" + name + "}", "1")
            for method in sorted(route.methods or []):
                response = await client.request(method, path)
                if response.status_code != 401:
                    failures.append(f"{method} {route.path} -> {response.status_code}")
    return failures


def _secured_app() -> FastAPI:
    return create_app(
        Settings(
            env="local",
            basic_auth_enabled=True,
            basic_auth_user="writer",
            basic_auth_password="not-a-real-secret",  # noqa: S106  (test value for a local app)
        )
    )


async def test_every_writer_route_answers_401_without_credentials() -> None:
    assert await unprotected_routes(_secured_app()) == []


async def test_the_sweep_detects_an_unprotected_route() -> None:
    # A deliberately open route outside the public area: proves the sweep is not vacuous.
    app = _secured_app()

    @app.get("/api/v1/leaky", operation_id="leaky")
    async def leaky() -> dict[str, str]:
        return {"data": "secret"}

    assert await unprotected_routes(app) == ["GET /api/v1/leaky -> 200"]
