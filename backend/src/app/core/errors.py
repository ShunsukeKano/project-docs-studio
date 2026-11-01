"""One error shape for the whole API: {"error": {"code", "message", "details"}}."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    default_message = "Something went wrong."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        self.headers = headers
        super().__init__(self.message)


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    default_message = "Authentication is required."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, headers={"WWW-Authenticate": 'Basic realm="studio"'})


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    default_message = "The requested resource does not exist."


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_error"
    default_message = "The request is not valid."


class AiDisabledError(AppError):
    status_code = 503
    code = "ai_disabled"
    default_message = "AI drafting is not available."


class AiUnavailableError(AppError):
    status_code = 502
    code = "ai_unavailable"
    default_message = "The AI draft could not be made. Please try again in a moment."


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    default_message = "Too many requests. Please wait a moment and try again."

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(headers={"Retry-After": str(max(1, retry_after_seconds))})


class VersionConflictError(AppError):
    status_code = 409
    code = "version_conflict"
    default_message = "The draft changed since you loaded it."

    def __init__(self, current_draft_version: int) -> None:
        super().__init__(details={"current_draft_version": current_draft_version})


class EmptyContentError(AppError):
    status_code = 422
    code = "empty_content"
    default_message = "A title and a body are required to publish."


class NotPublishedError(AppError):
    status_code = 409
    code = "not_published"
    default_message = "The article is not published."


class VersionIsLiveError(AppError):
    status_code = 409
    code = "version_is_live"
    default_message = "The live version cannot be deleted."


class SlugConflictError(AppError):
    status_code = 409
    code = "slug_conflict"
    default_message = "That slug is already in use."


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


_RESPONSE_DESCRIPTIONS = {
    401: "Missing or wrong credentials (code `unauthorized`).",
    404: "Not found (code `not_found`).",
    409: "Conflict (`version_conflict`, `slug_conflict`, `not_published` or `version_is_live`).",
    422: "Invalid input (`validation_error`) or empty content (`empty_content`). Nothing changes.",
    429: "Too many requests (code `rate_limited`). The `Retry-After` header says how long to wait.",
    502: "The AI draft could not be made (code `ai_unavailable`). No internal detail is given.",
    503: "AI drafting is switched off (code `ai_disabled`).",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """The `responses=` entry for a route: the error envelope per listed status (401 always)."""
    return {
        code: {"model": ErrorEnvelope, "description": _RESPONSE_DESCRIPTIONS[code]}
        for code in sorted({401, *codes})
    }


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details),
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Keep only plain fields: the raw error list can hold objects that are not JSON.
    problems = [
        {"loc": [str(part) for part in e["loc"]], "msg": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        error_body(
            ValidationFailedError.code, ValidationFailedError.default_message, {"errors": problems}
        ),
        status_code=422,
    )


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = NotFoundError.code if exc.status_code == 404 else "http_error"
    return JSONResponse(
        error_body(code, str(exc.detail)), status_code=exc.status_code, headers=exc.headers
    )


async def _handle_unexpected(_: Request, __: Exception) -> JSONResponse:
    # The cause is logged by the server; the client never sees internals.
    return JSONResponse(error_body("internal_error", AppError.default_message), status_code=500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
