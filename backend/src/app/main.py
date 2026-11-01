"""Application factory. Writer routes sit behind Basic auth; public routes and /healthz do not."""

import contextvars
import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi

from app.api.v1.routes import ai as ai_routes
from app.api.v1.routes import articles as article_routes
from app.api.v1.routes import public as public_routes
from app.core.config import Settings, load_settings, warn_if_authentication_is_off
from app.core.errors import install_error_handlers
from app.core.security import require_basic_auth
from app.db.session import create_engine, create_session_factory
from app.domains.ai.generator import ClaudeDraftGenerator, DraftGenerator
from app.domains.ai.limiter import RateLimiter

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


# FastAPI adds a default 422 response to any route that has parameters. These routes take a plain
# string and cannot fail validation, so the entry would document something that never happens.
NO_VALIDATION_ERROR = {"getPublicArticle"}


def _tidy_openapi(app: FastAPI) -> Callable[[], dict[str, Any]]:
    """Describe validation errors with the real error envelope instead of FastAPI's default."""

    def build() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title, version=app.version, routes=app.routes, description=app.description
        )
        envelope = {"$ref": "#/components/schemas/ErrorEnvelope"}
        for item in schema["paths"].values():
            for operation in item.values():
                responses = operation.get("responses", {})
                if operation.get("operationId") in NO_VALIDATION_ERROR:
                    responses.pop("422", None)
                elif "422" in responses:
                    responses["422"]["description"] = "Invalid input (code `validation_error`)."
                    responses["422"]["content"] = {"application/json": {"schema": envelope}}
        # Writer operations (everything under /api/v1 except /public) need Basic authentication.
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["basicAuth"] = {
            "type": "http",
            "scheme": "basic",
            "description": "Credentials come from BASIC_AUTH_USER and BASIC_AUTH_PASSWORD.",
        }
        for path, item in schema["paths"].items():
            if path.startswith("/api/v1/") and not path.startswith("/api/v1/public/"):
                for operation in item.values():
                    operation["security"] = [{"basicAuth": []}]
        for name in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(name, None)
        app.openapi_schema = schema
        return schema

    return build


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or load_settings()
    warn_if_authentication_is_off(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url) if settings.database_url else None
        app.state.session_factory = create_session_factory(engine) if engine else None
        try:
            yield
        finally:
            if engine:
                await engine.dispose()

    docs_enabled = not settings.is_prod
    app = FastAPI(
        title="Docs Studio API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings
    app.openapi = _tidy_openapi(app)  # type: ignore[method-assign]
    app.state.session_factory = None
    # Optional extra: the generator exists only when AI_ENABLED is true (tests replace it).
    ai_generator: DraftGenerator | None = (
        ClaudeDraftGenerator(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_tokens=settings.ai_max_output_tokens,
        )
        if settings.ai_enabled
        else None
    )
    app.state.ai_generator = ai_generator
    app.state.ai_limiter = RateLimiter(settings.ai_requests_per_minute)
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        # Writer responses are private: they must never be stored by a cache.
        path = request.url.path
        if path.startswith("/api/v1/") and not path.startswith("/api/v1/public/"):
            # A route may already have set a stricter value (the AI stream adds no-transform).
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # One dependency for the whole writer router, so a new route cannot forget it.
    writer = APIRouter(prefix="/api/v1", dependencies=[Depends(require_basic_auth)])
    public = APIRouter(prefix="/api/v1/public")
    app.state.writer_router = writer
    app.state.public_router = public

    @app.get("/healthz", operation_id="healthz", include_in_schema=True)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}  # no database access: this only says the process is up

    # Routes are added to these routers by the user-story phases (see tasks.md).
    writer.include_router(article_routes.router)
    writer.include_router(ai_routes.router)
    app.include_router(writer)
    public.include_router(public_routes.router)
    app.include_router(public)
    return app


app = create_app()
