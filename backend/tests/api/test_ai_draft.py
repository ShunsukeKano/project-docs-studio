"""The optional AI operations: off by default, a streamed proposal only, limited, protected."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.errors import AiUnavailableError
from app.db.session import create_session_factory
from app.domains.ai.schemas import AiDraftRequest
from app.main import create_app
from tests.conftest import TEST_WRITER_PASSWORD, TEST_WRITER_USER

DRAFT = "/api/v1/ai/draft"
STATUS = "/api/v1/ai/status"
SECRET = "sk-ant-test-not-a-real-key"
PIECES = ["## Proposed", "\n\nA first ", "paragraph.\n", "\n- one\n- two"]


class FakeGenerator:
    def __init__(self) -> None:
        self.calls: list[AiDraftRequest] = []
        self.error_before: Exception | None = None
        self.error_after_first: Exception | None = None

    async def stream(self, request: AiDraftRequest) -> AsyncIterator[str]:
        self.calls.append(request)
        if self.error_before:
            raise self.error_before
        for number, piece in enumerate(PIECES):
            if number == 1 and self.error_after_first:
                raise self.error_after_first
            yield piece


def build(
    engine: AsyncEngine,
    *,
    enabled: bool,
    authentication: bool = False,
    requests_per_minute: int = 5,
) -> tuple[httpx.AsyncClient, FakeGenerator]:
    settings = Settings(
        env="local",
        ai_enabled=enabled,
        anthropic_api_key=SecretStr(SECRET if enabled else ""),
        ai_requests_per_minute=requests_per_minute,
        basic_auth_enabled=authentication,
        basic_auth_user=TEST_WRITER_USER if authentication else "",
        basic_auth_password=SecretStr(TEST_WRITER_PASSWORD if authentication else ""),
    )
    app = create_app(settings)
    app.state.session_factory = create_session_factory(engine)
    fake = FakeGenerator()
    if enabled:
        app.state.ai_generator = fake  # the real client is never used in a test
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return client, fake


def events(response: httpx.Response) -> list[dict[str, Any]]:
    """The server-sent events in a response body, as dictionaries."""
    found: list[dict[str, Any]] = []
    for block in response.text.split("\n\n"):
        if block.startswith("data: "):
            found.append(json.loads(block[len("data: ") :]))
    return found


async def counts(engine: AsyncEngine) -> tuple[int, int]:
    async with engine.connect() as conn:
        articles = (await conn.execute(text("SELECT count(*) FROM articles"))).scalar_one()
        versions = (await conn.execute(text("SELECT count(*) FROM article_versions"))).scalar_one()
    return int(articles), int(versions)


class TestOffByDefault:
    async def test_the_status_says_it_is_off(self, engine: AsyncEngine) -> None:
        client, _ = build(engine, enabled=False)
        async with client:
            response = await client.get(STATUS)
        assert response.status_code == 200
        assert response.json() == {"enabled": False}

    async def test_the_draft_operation_answers_not_available(self, engine: AsyncEngine) -> None:
        client, _ = build(engine, enabled=False)
        async with client:
            response = await client.post(DRAFT, json={"title": "Anything"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ai_disabled"

    def test_the_default_settings_have_it_off(self) -> None:
        assert Settings(env="local").ai_enabled is False

    def test_turning_it_on_without_a_key_refuses_to_start(self) -> None:
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            Settings(env="local", ai_enabled=True)


class TestStreamedProposal:
    async def test_the_body_arrives_in_several_pieces_and_nothing_is_created(
        self, engine: AsyncEngine
    ) -> None:
        client, fake = build(engine, enabled=True)
        async with client:
            status = await client.get(STATUS)
            response = await client.post(
                DRAFT,
                json={
                    "title": "How to start",
                    "tags": ["Guide", "api"],
                    "notes": "- install\n- configure",
                    "instructions": "Be brief",
                },
            )
        assert status.json() == {"enabled": True}
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        parsed = events(response)
        deltas = [e for e in parsed if e["type"] == "delta"]
        assert len(deltas) == len(PIECES) > 1  # several pieces, not one block
        assert "".join(e["text"] for e in deltas) == "".join(PIECES)
        assert parsed[-1] == {"type": "done"}
        assert all(e["type"] != "error" for e in parsed)

        (call,) = fake.calls
        assert call.title == "How to start"
        assert call.tags == ["guide", "api"]
        assert call.notes == "- install\n- configure"
        assert call.instructions == "Be brief"
        assert await counts(engine) == (0, 0)  # no article, no snapshot

    async def test_a_title_alone_is_enough(self, engine: AsyncEngine) -> None:
        client, fake = build(engine, enabled=True)
        async with client:
            response = await client.post(DRAFT, json={"title": "Just a title"})
        assert response.status_code == 200
        assert fake.calls[0].tags == []
        assert fake.calls[0].notes == ""

    async def test_nothing_buffers_or_stores_the_stream(self, engine: AsyncEngine) -> None:
        client, _ = build(engine, enabled=True)
        async with client:
            response = await client.post(DRAFT, json={"title": "x"})
        cache_control = response.headers["cache-control"]
        assert "no-store" in cache_control
        assert "no-transform" in cache_control
        assert response.headers["x-accel-buffering"] == "no"


class TestInputLimits:
    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"title": ""},
            {"title": "   "},
            {"title": "x" * 201},
            {"title": "ok", "tags": ["t"] * 11},
            {"title": "ok", "tags": ["x" * 31]},
            {"title": "ok", "notes": "n" * 5001},
            {"title": "ok", "instructions": "y" * 1001},
            {"title": "ok", "unknown": 1},
        ],
    )
    async def test_bad_input_is_refused_before_any_model_call(
        self, engine: AsyncEngine, payload: dict[str, Any]
    ) -> None:
        client, fake = build(engine, enabled=True)
        async with client:
            response = await client.post(DRAFT, json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert fake.calls == []

    async def test_the_limits_themselves_are_allowed(self, engine: AsyncEngine) -> None:
        client, fake = build(engine, enabled=True)
        async with client:
            response = await client.post(
                DRAFT,
                json={
                    "title": "x" * 200,
                    "tags": [f"t{i}" for i in range(10)],
                    "notes": "n" * 5000,
                    "instructions": "y" * 1000,
                },
            )
        assert response.status_code == 200
        assert len(fake.calls) == 1


class TestRateLimit:
    async def test_too_many_requests_get_429_and_no_model_call(self, engine: AsyncEngine) -> None:
        client, fake = build(engine, enabled=True, requests_per_minute=2)
        async with client:
            codes = [(await client.post(DRAFT, json={"title": "t"})).status_code for _ in range(4)]
            blocked = await client.post(DRAFT, json={"title": "t"})
        assert codes == [200, 200, 429, 429]
        assert blocked.json()["error"]["code"] == "rate_limited"
        assert int(blocked.headers["retry-after"]) >= 1
        assert len(fake.calls) == 2

    async def test_a_refused_request_does_not_use_up_the_allowance(
        self, engine: AsyncEngine
    ) -> None:
        client, fake = build(engine, enabled=True, requests_per_minute=1)
        async with client:
            await client.post(DRAFT, json={"title": ""})  # invalid: 422
            ok = await client.post(DRAFT, json={"title": "valid"})
        assert ok.status_code == 200
        assert len(fake.calls) == 1


class TestFailures:
    async def test_a_failure_before_the_first_piece_is_a_normal_502(
        self, engine: AsyncEngine
    ) -> None:
        client, fake = build(engine, enabled=True)
        fake.error_before = AiUnavailableError()
        async with client:
            response = await client.post(DRAFT, json={"title": "t"})
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "ai_unavailable"
        assert await counts(engine) == (0, 0)

    async def test_a_failure_in_the_middle_is_an_error_event_after_the_text_that_arrived(
        self, engine: AsyncEngine
    ) -> None:
        client, fake = build(engine, enabled=True)
        fake.error_after_first = AiUnavailableError("The draft was cut off.")
        async with client:
            response = await client.post(DRAFT, json={"title": "t"})
        assert response.status_code == 200  # the stream had already started
        parsed = events(response)
        assert [e["type"] for e in parsed] == ["delta", "error"]
        assert parsed[0]["text"] == PIECES[0]
        assert parsed[1]["code"] == "ai_unavailable"
        assert parsed[1]["message"] == "The draft was cut off."
        assert await counts(engine) == (0, 0)

    async def test_an_unexpected_error_in_the_middle_does_not_leak_internals(
        self, engine: AsyncEngine
    ) -> None:
        client, fake = build(engine, enabled=True)
        fake.error_after_first = RuntimeError(f"secret detail {SECRET}")
        async with client:
            response = await client.post(DRAFT, json={"title": "t"})
        assert SECRET not in response.text
        assert "secret detail" not in response.text
        last = events(response)[-1]
        assert last["type"] == "error"
        assert last["code"] == "ai_unavailable"

    async def test_an_unexpected_error_before_the_first_piece_does_not_leak_internals(
        self, engine: AsyncEngine
    ) -> None:
        client, fake = build(engine, enabled=True)
        fake.error_before = RuntimeError(f"secret detail {SECRET}")
        async with client:
            with pytest.raises(RuntimeError):  # the test transport re-raises server errors
                await client.post(DRAFT, json={"title": "t"})


class TestProtection:
    @pytest.mark.parametrize(("method", "path"), [("GET", STATUS), ("POST", DRAFT)])
    async def test_no_credentials_returns_401_first(
        self, engine: AsyncEngine, method: str, path: str
    ) -> None:
        client, fake = build(engine, enabled=True, authentication=True)
        async with client:
            response = await client.request(method, path, json={"title": ""})
        assert response.status_code == 401
        assert fake.calls == []

    async def test_right_credentials_work(self, engine: AsyncEngine) -> None:
        client, _ = build(engine, enabled=True, authentication=True)
        auth = httpx.BasicAuth(TEST_WRITER_USER, TEST_WRITER_PASSWORD)
        async with client:
            response = await client.post(DRAFT, json={"title": "t"}, auth=auth)
        assert response.status_code == 200


class TestSecretsAndLogs:
    async def test_neither_the_key_nor_the_text_is_logged(
        self, engine: AsyncEngine, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        client, fake = build(engine, enabled=True)
        fake.error_before = AiUnavailableError()
        private_text = "a-very-private-phrase"
        async with client:
            await client.post(
                DRAFT,
                json={"title": private_text, "notes": private_text, "instructions": private_text},
            )
        logged = caplog.text
        assert SECRET not in logged
        assert private_text not in logged

    def test_the_settings_do_not_print_the_key(self) -> None:
        settings = Settings(env="local", ai_enabled=True, anthropic_api_key=SecretStr(SECRET))
        assert SECRET not in repr(settings)
        assert SECRET not in str(settings)
