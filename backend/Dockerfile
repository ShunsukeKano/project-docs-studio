# FastAPI (src layout). On Cloud Run, specify --port=8000 (the CMD honours $PORT)
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.13@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:$PATH"
WORKDIR /srv

# Install dependencies first (this layer is reused when only the code changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# The app itself plus migrations (the Compose "migrate" service and the Cloud Run Job run alembic)
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY db-automation-apply ./db-automation-apply
RUN uv sync --frozen --no-dev

# Test image: adds the dev dependencies and the tests (used by `docker compose --profile test`)
FROM base AS test
RUN uv sync --frozen
COPY tests ./tests
COPY openapi.json ./openapi.json
CMD ["pytest", "-q"]

FROM base AS run
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
