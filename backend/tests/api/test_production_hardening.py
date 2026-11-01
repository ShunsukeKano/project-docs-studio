"""Start-up refusals and production settings (US8, FR-030)."""

import logging

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings, load_settings
from app.db.session import create_session_factory
from app.main import create_app

SECRET = "prod-test-secret-value"  # a test value, never a real credential


def prod_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "prod",
        "basic_auth_enabled": True,
        "basic_auth_user": "writer",
        "basic_auth_password": SECRET,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class TestRefusingToStart:
    def test_prod_without_authentication_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="BASIC_AUTH_ENABLED must be true"):
            prod_settings(basic_auth_enabled=False)

    @pytest.mark.parametrize("env", ["prod", "local"])
    @pytest.mark.parametrize(
        "overrides",
        [
            {"basic_auth_user": ""},
            {"basic_auth_password": ""},
            {"basic_auth_user": "", "basic_auth_password": ""},
        ],
    )
    def test_enabled_with_an_empty_credential_is_refused_in_any_environment(
        self, env: str, overrides: dict[str, str]
    ) -> None:
        with pytest.raises(ValidationError, match="must both be set"):
            prod_settings(env=env, **overrides)

    def test_the_environment_variables_are_checked_the_same_way(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("BASIC_AUTH_ENABLED", "false")
        with pytest.raises(ValidationError):
            load_settings()
        monkeypatch.setenv("BASIC_AUTH_ENABLED", "true")
        monkeypatch.setenv("BASIC_AUTH_USER", "")
        monkeypatch.setenv("BASIC_AUTH_PASSWORD", "")
        with pytest.raises(ValidationError):
            create_app()

    def test_a_valid_production_configuration_starts(self) -> None:
        assert create_app(prod_settings()) is not None


class TestLocalWithAuthenticationOff:
    async def test_writer_routes_work_without_credentials_and_a_warning_is_logged(
        self, caplog: pytest.LogCaptureFixture, engine: AsyncEngine
    ) -> None:
        from tests.conftest import _build_app

        with caplog.at_level(logging.WARNING):
            app = _build_app(engine, authentication=False)
        assert "BASIC_AUTH_ENABLED is false" in caplog.text
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            assert (await http.get("/api/v1/articles")).status_code == 200


class TestProductionSurface:
    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    async def test_interactive_documentation_is_off_in_production(self, path: str) -> None:
        transport = httpx.ASGITransport(app=create_app(prod_settings()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            assert (await http.get(path)).status_code == 404

    @pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
    async def test_it_is_on_for_a_local_run(self, path: str) -> None:
        app = create_app(Settings(env="local", basic_auth_enabled=False))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            assert (await http.get(path)).status_code == 200

    async def test_no_cors_headers_are_sent(self) -> None:
        transport = httpx.ASGITransport(app=create_app(prod_settings()))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            plain = await http.get("/healthz", headers={"Origin": "https://evil.example"})
            preflight = await http.options(
                "/api/v1/articles",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "POST",
                },
            )
        for response in (plain, preflight):
            assert not any(name.lower().startswith("access-control-") for name in response.headers)

    async def test_credentials_and_the_authorization_header_never_appear_in_logs(
        self, caplog: pytest.LogCaptureFixture, engine: AsyncEngine
    ) -> None:
        import base64

        caplog.set_level(logging.DEBUG)
        token = base64.b64encode(f"writer:{SECRET}".encode()).decode()
        wrong = base64.b64encode(b"writer:wrong-password-xyz").decode()
        app = create_app(prod_settings())
        app.state.session_factory = create_session_factory(engine)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            await http.get("/api/v1/articles", headers={"Authorization": f"Basic {token}"})
            await http.get("/api/v1/articles", headers={"Authorization": f"Basic {wrong}"})
            await http.get("/api/v1/articles")
        logged = caplog.text.lower()
        for forbidden in (SECRET, token, wrong, "wrong-password-xyz", "authorization"):
            assert forbidden.lower() not in logged

    def test_the_settings_do_not_print_the_password(self) -> None:
        settings = prod_settings()
        assert SECRET not in repr(settings)
        assert SECRET not in str(settings)
