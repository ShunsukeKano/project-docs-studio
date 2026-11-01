"""Optional AI operations (writer routes). They stream a proposal and store nothing."""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.errors import AiDisabledError, AiUnavailableError, AppError, error_responses
from app.domains.ai.generator import DraftGenerator
from app.domains.ai.limiter import RateLimiter
from app.domains.ai.schemas import AiDraftRequest, AiStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["writer"])

# The failure message a writer sees when something unexpected breaks after streaming has started.
GENERIC_FAILURE = AiUnavailableError.default_message


def _event(payload: dict[str, str]) -> str:
    """One server-sent event: a `data:` line holding JSON, then a blank line."""
    return f"data: {json.dumps(payload)}\n\n"


async def _events(first: str, rest: AsyncIterator[str]) -> AsyncIterator[str]:
    yield _event({"type": "delta", "text": first})
    try:
        async for piece in rest:
            yield _event({"type": "delta", "text": piece})
    except AppError as error:
        yield _event({"type": "error", "code": error.code, "message": error.message})
        return
    except Exception:
        # Anything else is logged without the text and shown to the writer without detail.
        logger.exception("AI draft stream failed")
        yield _event({"type": "error", "code": AiUnavailableError.code, "message": GENERIC_FAILURE})
        return
    yield _event({"type": "done"})


@router.get(
    "/ai/status",
    operation_id="getAiStatus",
    summary="Is AI drafting switched on?",
    response_model=AiStatus,
    responses=error_responses(),
)
async def get_ai_status(request: Request) -> AiStatus:
    return AiStatus(enabled=request.app.state.settings.ai_enabled)


@router.post(
    "/ai/draft",
    operation_id="generateDraft",
    summary="Stream a proposed body from the writer's title, tags and notes (nothing is saved)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-sent events: `delta` pieces of the body, then `done`/`error`.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        **error_responses(422, 429, 502, 503),
    },
)
async def generate_draft(data: AiDraftRequest, request: Request) -> StreamingResponse:
    generator: DraftGenerator | None = request.app.state.ai_generator
    if generator is None:
        raise AiDisabledError()
    limiter: RateLimiter = request.app.state.ai_limiter
    limiter.check()  # after validation, so a refused request does not use up the allowance

    pieces = generator.stream(data).__aiter__()
    try:
        # Wait for the first piece here, so a failure at the start is a normal error response
        # (a status code and the usual envelope) rather than an event inside a 200 stream.
        first = await pieces.__anext__()
    except StopAsyncIteration as error:
        raise AiUnavailableError() from error

    return StreamingResponse(
        _events(first, pieces),
        media_type="text/event-stream",
        headers={
            # Writer responses are private; no-transform and the buffering hint keep proxies from
            # holding the stream back.
            "Cache-Control": "no-store, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
