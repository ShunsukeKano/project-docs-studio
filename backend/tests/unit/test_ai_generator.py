"""The Claude draft generator: the request it sends and how the streamed text is handled.

A fake client stands in for the SDK, so nothing here reaches the network.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import SecretStr

from app.core.errors import AiUnavailableError
from app.domains.ai.generator import ClaudeDraftGenerator
from app.domains.ai.schemas import AiDraftRequest

REQUEST = AiDraftRequest(
    title="Getting started", tags=["guide"], notes="Rough outline", instructions="Keep it short"
)
PIECES = ["## Why", " it matters\n\n", "Short ", "and clear."]


class FakeStream:
    def __init__(
        self,
        pieces: list[str],
        *,
        stop_reason: str = "end_turn",
        enter_error: Exception | None = None,
        error_after: int | None = None,
        error: Exception | None = None,
    ) -> None:
        self.pieces = pieces
        self.stop_reason = stop_reason
        self.enter_error = enter_error
        self.error_after = error_after
        self.error = error

    async def __aenter__(self) -> "FakeStream":
        if self.enter_error:
            raise self.enter_error
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    @property
    def text_stream(self) -> AsyncIterator[str]:
        async def pieces() -> AsyncIterator[str]:
            for number, piece in enumerate(self.pieces):
                if self.error_after is not None and number == self.error_after:
                    assert self.error is not None
                    raise self.error
                yield piece

        return pieces()

    async def get_final_message(self) -> Any:
        return SimpleNamespace(stop_reason=self.stop_reason)


class FakeMessages:
    def __init__(self, stream: FakeStream) -> None:
        self._stream = stream
        self.calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        return self._stream


def make(messages: FakeMessages, **overrides: Any) -> ClaudeDraftGenerator:
    return ClaudeDraftGenerator(
        api_key=SecretStr("test-key"),
        model=overrides.get("model", "claude-sonnet-4-6"),
        max_tokens=overrides.get("max_tokens", 3000),
        client=SimpleNamespace(messages=messages),  # type: ignore[arg-type]
    )


async def collect(generator: ClaudeDraftGenerator) -> list[str]:
    return [piece async for piece in generator.stream(REQUEST)]


async def test_the_text_arrives_piece_by_piece_in_order() -> None:
    pieces: list[str] = []
    async for piece in make(FakeMessages(FakeStream(PIECES))).stream(REQUEST):
        pieces.append(piece)
    assert pieces == PIECES  # several pieces, not one block


async def test_the_request_has_the_model_and_the_token_cap() -> None:
    messages = FakeMessages(FakeStream(PIECES))
    await collect(make(messages))

    (call,) = messages.calls
    assert call["model"] == "claude-sonnet-4-6"
    assert call["max_tokens"] == 3000
    assert "Markdown" in call["system"]


async def test_the_request_has_no_prefill_and_no_sampling_parameters() -> None:
    messages = FakeMessages(FakeStream(PIECES))
    await collect(make(messages))

    (call,) = messages.calls
    assert call["messages"][-1]["role"] == "user"  # a trailing assistant turn is a prefill
    for forbidden in ("temperature", "top_p", "top_k", "thinking", "output_config"):
        assert forbidden not in call


async def test_the_title_tags_notes_and_instructions_reach_the_model_as_the_user_turn() -> None:
    messages = FakeMessages(FakeStream(PIECES))
    await collect(make(messages))

    content = messages.calls[0]["messages"][-1]["content"]
    assert "Getting started" in content
    assert "guide" in content
    assert "Rough outline" in content
    assert "Keep it short" in content


async def test_notes_and_instructions_are_left_out_when_empty() -> None:
    messages = FakeMessages(FakeStream(PIECES))
    async for _ in make(messages).stream(AiDraftRequest(title="Only a title")):
        pass

    content = messages.calls[0]["messages"][-1]["content"]
    assert "Only a title" in content
    assert "Notes" not in content
    assert "Instructions" not in content


async def test_the_model_is_configurable() -> None:
    messages = FakeMessages(FakeStream(PIECES))
    await collect(make(messages, model="claude-sonnet-5-5"))
    assert messages.calls[0]["model"] == "claude-sonnet-5-5"


async def test_nothing_at_all_is_a_failure() -> None:
    with pytest.raises(AiUnavailableError):
        await collect(make(FakeMessages(FakeStream([]))))


async def test_a_refusal_after_some_text_is_a_failure_at_the_end() -> None:
    generator = make(FakeMessages(FakeStream(PIECES, stop_reason="refusal")))
    received: list[str] = []
    with pytest.raises(AiUnavailableError):
        async for piece in generator.stream(REQUEST):
            received.append(piece)
    assert received == PIECES  # what arrived was already delivered


async def test_a_cut_off_reply_says_so() -> None:
    generator = make(FakeMessages(FakeStream(PIECES, stop_reason="max_tokens")))
    with pytest.raises(AiUnavailableError) as raised:
        await collect(generator)
    assert "cut off" in raised.value.message.lower()


def api_errors() -> list[Exception]:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return [
        anthropic.APIConnectionError(request=request),
        anthropic.RateLimitError(
            "slow down", response=httpx2.Response(429, request=request), body=None
        ),
        anthropic.APIStatusError("boom", response=httpx2.Response(500, request=request), body=None),
        anthropic.AuthenticationError(
            "bad key", response=httpx2.Response(401, request=request), body=None
        ),
    ]


def assert_generic(message: str) -> None:
    for leak in ("key", "401", "429", "500", "anthropic", "boom"):
        assert leak not in message.lower()


@pytest.mark.parametrize("error", api_errors())
async def test_an_sdk_error_at_the_start_is_a_generic_failure(error: Exception) -> None:
    generator = make(FakeMessages(FakeStream(PIECES, enter_error=error)))
    with pytest.raises(AiUnavailableError) as raised:
        await collect(generator)
    assert_generic(raised.value.message)


@pytest.mark.parametrize("error", api_errors())
async def test_an_sdk_error_in_the_middle_is_a_generic_failure(error: Exception) -> None:
    generator = make(FakeMessages(FakeStream(PIECES, error_after=2, error=error)))
    received: list[str] = []
    with pytest.raises(AiUnavailableError) as raised:
        async for piece in generator.stream(REQUEST):
            received.append(piece)
    assert received == PIECES[:2]
    assert_generic(raised.value.message)
