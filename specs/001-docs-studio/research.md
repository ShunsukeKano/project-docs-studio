# Research: Docs Studio

Phase 0 output of `/speckit-plan`. Each entry records the **decision**, the **rationale** and the **alternatives considered**. There are no open `NEEDS CLARIFICATION` items. The full reasoning behind most entries is in `docs/requirements.md` (section 13) and `docs/nextjs-fastapi-architecture.html`.

## R-01 Concurrency token: `expected_draft_version` in the request body

- **Decision**: Edit, Restore and Publish carry `expected_draft_version` in the request body. A mismatch returns 409 with code `version_conflict` and the current `draft_version` in `details`. Unpublish and Delete version carry no token.
- **Rationale**: The screen can offer "reload or resubmit" using the version in the error body, and a body field is simpler to implement and to test than a header. Every change to a draft bumps `draft_version`, so a stale screen can never overwrite newer work.
- **Alternatives considered**: `If-Match` with an ETag and 412 (rejected: more plumbing, the version would live in a header that Server Actions must forward); a timestamp (rejected: clock and precision problems); pessimistic locking across requests (rejected: locks held while a person types).

## R-02 Locking and isolation

- **Decision**: Every writer operation takes the article row lock first (`SELECT … FOR UPDATE`, or one conditional `UPDATE`) and decides against the locked row. Isolation is `READ COMMITTED`. The lock order is always the article row, then version rows. `SET LOCAL lock_timeout = '3s'`; a lock timeout maps to 503.
- **Rationale**: The decision (version matches? same as live? is this the protected version?) must be made on data nobody else can change. With `READ COMMITTED`, a waiting `UPDATE` re-checks its `WHERE` against the new row, which is exactly the behaviour needed. A fixed lock order prevents deadlocks between Publish, Delete and Restore.
- **Alternatives considered**: `REPEATABLE READ` or `SERIALIZABLE` (rejected: waits turn into serialization failures that need retries); advisory locks (rejected: the row lock already gives per-article serialization); optimistic-only checks without a lock (rejected: Publish and Delete could interleave).

## R-03 Version numbers come from a per-article counter

- **Decision**: `articles.last_version_number` is incremented under the row lock, and the new snapshot takes that number. Numbers are never reused, even after a deletion.
- **Rationale**: `MAX(version_number) + 1` only avoids reuse by accident (the highest version happens to be undeletable) and would break if a non-live version could be the highest. A counter column that never decreases gives the guarantee directly. A database sequence is the wrong tool: it is global and leaves gaps after a rollback.
- **Alternatives considered**: `MAX + 1` (rejected, see above); a Postgres sequence per article (rejected: gaps after rollback, one sequence per article).

## R-04 The protected version and Delete

- **Decision**: The protected version is the one `current_published_version_id` points to, in every state, including after Unpublish. Delete takes the same row lock as Publish, returns 409 `version_is_live` for the protected version, 404 for a missing number, and 204 on success. A foreign-key violation (SQLSTATE 23503) is mapped to the same 409.
- **Rationale**: "Live" is ambiguous after Unpublish, but the assignment also says the last published snapshot must survive Unpublish. Defining the protected version by the pointer satisfies both. Sharing the lock stops a Delete racing a Publish from leaving a dangling pointer or surfacing a 500. The composite foreign key (`ON DELETE RESTRICT`) is the backstop.
- **Alternatives considered**: Protecting only while the status is `published` (rejected: it would let the last published snapshot be deleted after Unpublish); soft delete (rejected: it adds states for no benefit).

## R-05 Idempotent Publish

- **Decision**: After the lock and the version check, and after the empty-content check, compare the draft's title, body and tags with the **live snapshot only**, row by row (`IS NOT DISTINCT FROM`). If equal, create nothing and leave `published_at`, the pointer and `draft_version` unchanged; if the article was unpublished, set it back to `published`; respond 200 (201 when a snapshot is created). Check order: version (409), then `empty_content` (422), then the idempotency check.
- **Rationale**: A row-wise comparison under the lock is exact, and no hash column has to stay in step with an immutable table. Comparing only with the live snapshot means a draft equal to an older version still creates a new one, which is the documented rule. Checking the version first stops a stale screen from succeeding by accident.
- **Alternatives considered**: A content hash column (rejected: extra column to keep in sync); comparing with all snapshots (rejected: it would block deliberately republishing an older text).

## R-06 Slug collision handling

- **Decision**: On create, if the slug is taken, append `-2`, `-3`, … (the smallest free number), shortening the base so the result stays within 100 characters, and return the stored slug. On a unique violation (SQLSTATE 23505) from a concurrent create, retry the numbering, up to 5 attempts; only if every attempt loses is 409 `slug_conflict` returned. The slug never changes after creation, and the guard trigger enforces that.
- **Rationale**: The unique constraint stays the guarantee, and the retry makes a race harmless (two creates get two slugs, never a 500).
- **Alternatives considered**: Rejecting duplicates with 409 (rejected: the optional feature was adopted); random suffixes (rejected: unfriendly URLs).

## R-07 Basic authentication: validated in FastAPI, forwarded by Next.js

- **Decision**: The writer router carries a router-level `Depends(require_basic_auth)`; the public router has none. Authentication is switched by the explicit setting `BASIC_AUTH_ENABLED`: it must be on in production (the app refuses to start otherwise), it is off by default in the local example environment file so a fresh local run needs no sign-in (as the assignment describes), and start-up logs a warning when it is off; enabled with an empty credential is a start-up error (never an implicit fallback). Credentials come from `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD`, are compared as UTF-8 bytes with `secrets.compare_digest` without short-circuiting, and are never logged. In production the app refuses to start unless authentication is on and both are non-empty, and `/docs` and `/openapi.json` are disabled. With authentication enabled, a test walks `app.routes` and fails if any route outside `/api/v1/public` and `/healthz` is reachable without credentials. In Next.js, `proxy.ts` (only when `BASIC_AUTH_ENABLED` is true) only checks that the header is present on `/studio/**`; Server Actions read the incoming header with `headers()` and pass it to the API on every call; on a 401 the page redirects to `/auth/challenge`, a route handler that returns `401` with `WWW-Authenticate: Basic`.
- **Rationale**: The API is exposed on Cloud Run, so only the API can be the authority; protecting just the screens would leave the writer API open. A Server Action has no `Authorization` header of its own and cannot set `WWW-Authenticate`, so the header must be forwarded explicitly and the challenge must come from a route handler. Basic authentication has no logout, which is accepted for this scope.
- **Alternatives considered**: IAM authentication on a private API (rejected: ID-token handling is excessive for an assignment where authentication is out of scope); a session cookie login (rejected: more code for the same protection); per-route checks (rejected: easy to forget on a new route).

## R-08 Public pages are dynamic and uncached

- **Decision**: Public pages use `export const dynamic = "force-dynamic"` and `cache: "no-store"` on the API fetch; `API_BASE_URL` is a runtime-only variable read lazily so `next build` needs no API. Writer responses carry `Cache-Control: no-store`; the public API sends no long-lived cache headers.
- **Rationale**: An unpublish must hide the article on the next request, so any cache could break the 404 requirement; a caching layer is also out of scope.
- **Alternatives considered**: Short revalidation windows (rejected: stale content up to the window, per-instance caches differ); tag-based revalidation (rejected: does not reach other instances).

## R-09 Markdown is rendered on the server with one shared sanitizer

- **Decision**: The body stays Markdown in storage. The public page renders it on the server (no raw HTML, `rehype-sanitize`, links limited to `http`, `https` and `mailto`). The writer's preview is a Client Component that imports the same `lib/markdown.ts`.
- **Rationale**: No Markdown library is shipped to readers, preview and published output cannot differ, and hostile content cannot run in a reader's browser. Tests cover a `javascript:` link and a raw `<script>`.
- **Alternatives considered**: Rendering in the backend (rejected: it would store or return HTML); a different renderer for the preview (rejected: the two could drift apart).

## R-10 Schema management: numbered SQL, applied by Alembic

- **Decision**: The DDL stays as numbered SQL files in `backend/db-automation-apply/` (source of truth). Alembic revision `0001` executes `001_schema.sql`; each future change adds a new numbered SQL file and an Alembic revision that executes it. An applied file is never edited. `make setup` runs `alembic upgrade head` on the development and test databases.
- **Rationale**: Alembic autogenerate cannot create the circular foreign key, the triggers or the CHECK constraints correctly, so the DDL is written by hand; Alembic still gives ordered, repeatable application and a version table.
- **Alternatives considered**: Autogenerated migrations (rejected: cannot express the guards); raw SQL applied by a script with no version table (rejected: no record of what is applied).

## R-11 Test database guard and isolation

- **Decision**: Tests read `TEST_DATABASE_URL`. Before any statement, the fixture aborts unless the database name ends in `_test` and the host is `localhost` or `127.0.0.1` (never a `/cloudsql` socket). A unit test covers the guard. Between tests, the data is reset with `BEGIN; SET LOCAL docs.allow_reset = 'on'; TRUNCATE articles, article_versions RESTART IDENTITY; COMMIT` (both tables in one statement because they reference each other; the snapshot table's `TRUNCATE` guard allows it only with that setting, which only the test fixture sets); concurrency tests use real, separate connections (pool of at least 2).
- **Rationale**: Production, development and test databases are separate, and a developer's shell normally has `DATABASE_URL` pointing at the development database through the proxy, so reusing it would make `make test` an easy accident. Real connections are the only way to test row locks.
- **Alternatives considered**: Reusing `DATABASE_URL` (rejected: dangerous); transaction-rollback isolation (rejected: it hides commit-time behaviour and cannot test two connections).

## R-12 One error envelope, declared in OpenAPI

- **Decision**: Every error is `{ "error": { "code", "message", "details" } }`. FastAPI's default 422 body is replaced by this envelope, and every route declares its error responses so the generated client types errors. Codes: `unauthorized`, `not_found`, `validation_error`, `version_conflict`, `empty_content`, `not_published`, `version_is_live`, `slug_conflict`.
- **Rationale**: The frontend branches on `error.code` only, and one shape means one handling path.
- **Alternatives considered**: Default FastAPI errors (rejected: two shapes); problem-details (rejected: no benefit for this size).

## R-13 Layering: the Service commits

- **Decision**: Router (HTTP only) → Service (business rules and the transaction; the only layer that commits; one session per request with one `async with session.begin()`; the tests target it) → Repository (thin: only the locking and snapshot SQL). A Service never raises `HTTPException`; errors are `AppError` subclasses converted in one handler. Sessions use `expire_on_commit=False`; locking reads use `populate_existing`.
- **Rationale**: One place owns the transaction, so atomicity is easy to reason about and to test. Pass-through repositories would only add code.
- **Alternatives considered**: Logic in routers (rejected: untestable without HTTP); a full repository layer (rejected: over-engineering for one aggregate).

## R-14 Timestamps use statement time

- **Decision**: `created_at`, `updated_at` and `published_at` use `clock_timestamp()` (statement time, in UTC); `updated_at` is maintained by the `articles_guard` trigger.
- **Rationale**: `now()` is the start of the transaction, so a Publish that waited for the lock would get an earlier time than the version before it.
- **Alternatives considered**: `now()` (rejected: the ordering problem above); setting times in application code (rejected: forgotten in some path).

## R-15 Types are generated from the contract

- **Decision**: The backend writes `openapi.json` (the script builds the app only, no database needed). The frontend generates its types and client with `openapi-typescript` and `openapi-fetch`; generated files are never edited. `make check-api` regenerates both and fails on any difference, and `make test` runs it. Every route sets `operation_id` explicitly to the camelCase name used in `contracts/openapi.yaml` (for example `createArticle`, `publishArticle`), so the generated function names are stable and match the contract.
- **Rationale**: One source of truth for request and response shapes.
- **Alternatives considered**: Hand-written types (rejected: they drift).

## R-16 Lists are capped, not paginated at scale

- **Decision**: Every list takes `limit` (default 20, maximum 100) and `offset`, with no total count. Large-scale pagination stays out of scope.
- **Rationale**: An unbounded list is cheap to abuse and costly to serve, but the assignment excludes real pagination.
- **Alternatives considered**: No limit (rejected); cursor pagination (rejected: out of scope).

## R-17 Local run with Docker Compose; Cloud Run is low priority

- **Decision**: A root `compose.yaml` runs the whole system from a fresh checkout: `db` (PostgreSQL 17, development), `db-test` (profile `test`, for tests), `migrate` (the backend image running `alembic upgrade head` once the database is healthy), `backend` and `frontend` (built from the Dockerfiles in `backend/` and `frontend/`). The README documents `docker compose up --build` and the native `make setup`, `make dev` and `make test` path. The Dockerfiles and `cloudbuild.yaml` are already drafted; they must not be described as verified until built and run (the Compose run verifies the Dockerfiles; Cloud Run is verified last). Assessors may use the local Compose run or the deployed Cloud Run site.
- **Rationale**: The assignment requires the project to run from a fresh checkout with a short setup command. With Docker, nothing else has to be installed or configured, which is the shortest and most reliable way. The deployed site stays available for assessors who prefer to install nothing. The Cloud Run work itself is still low priority because the assignment puts deployment out of scope.
- **Alternatives considered**: No Docker, with assessors installing PostgreSQL themselves (rejected: weaker than the assignment asks); Docker for the database only (rejected: assessors would still need Python and Node); an embedded database such as SQLite (rejected: the schema relies on PostgreSQL features such as triggers and array columns).

## R-18 Explicitly excluded

- **AI draft generation (FR-17 in `docs/requirements.md`)**: excluded. If it is ever built, it uses the Claude API with prepaid credit, so the spend cannot exceed the deposited amount; it returns a proposal and never writes. Vertex AI was considered and rejected because it can be called without limit.
- **Save as Version, Diff View**: not adopted.
- **Any caching layer**: not built (R-08).

## R-19 Styling: Tailwind CSS, no component library

- **Decision**: The interface is styled with Tailwind CSS only: a neutral palette with one accent colour, a system font stack, generous whitespace, a centred readable content width, a handful of small shared components (`button`, `input`, `textarea`, `tag`, `status-badge`, `empty-state`) in `frontend/src/components/ui/`, visible keyboard focus, and responsive layouts from phone to desktop width. Light theme only. Styling is a **time-boxed polish pass after the functionality and its tests** (see `tasks.md`).
- **Rationale**: Utility classes give a consistent, modern look with very little code and no separate design system, and the time box keeps the assessed work (the invariants and their tests) ahead of looks, which the assignment says are only a tie-breaker.
- **Alternatives considered**: A component library such as shadcn/ui or MUI (rejected: extra dependency and setup time for a minimal interface); plain CSS or CSS modules (rejected: more code to keep consistent); no styling (rejected: the interface should still look clean).
