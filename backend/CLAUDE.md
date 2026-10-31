# backend

FastAPI (src layout: `src/app/`), SQLAlchemy 2.0 (async), Alembic and PostgreSQL. Packages are managed with uv.
The shared rules (the Spec Kit workflow, `docs/`, the language policy) are in the root `../CLAUDE.md`.

- Layers: router (HTTP only) → service (business rules, state transitions and the transaction; the only layer that commits) → repository (thin; SQL only). A service never raises `HTTPException`.
- Input and output schemas are separate for Create, Update and Read, and every response goes through a `response_model`. Every route sets `operation_id` explicitly, in the camelCase used in `specs/001-docs-studio/contracts/openapi.yaml`.
- Errors use one shape: `{"error": {"code", "message", "details"}}`.
- The database is PostgreSQL: Cloud SQL in production, and PostgreSQL 17 started by Docker Compose (`db`, `db-test` in the root `compose.yaml`) for local runs. The target is chosen with the `DATABASE_URL` environment variable, so Cloud SQL through the Auth Proxy also works.
- Tests live in `tests/` (outside `src`). **Tests use only a dedicated database whose name ends in `_test`**, read from `TEST_DATABASE_URL`, and refuse to run against any other database.
- Writer routes need Basic authentication, switched by the explicit setting `BASIC_AUTH_ENABLED` (required in production, where the app refuses to start without it; off by default for a local run, with a start-up warning). `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` come from environment variables, are never written in code, and are compared with `secrets.compare_digest`. The public API (`/api/v1/public/*`) needs none.
- The DDL is stored in `db-automation-apply/` as numbered SQL files (`001_schema.sql`). That SQL is the source of truth, and section 7 of `docs/nextjs-fastapi-architecture.html` follows it. Never edit an applied file; add a new numbered file for a change.
- Migrations: `uv run alembic upgrade head`.
- `Dockerfile` and `cloudbuild.yaml` are in this folder. Docker Compose builds the `Dockerfile` for the local run (`docker compose up --build` from the repository root); Cloud Build builds it for Cloud Run (low priority).
