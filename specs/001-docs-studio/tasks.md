---

description: "Task list for the Docs Studio feature"
---

# Tasks: Docs Studio

**Input**: Design documents from `specs/001-docs-studio/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml), [quickstart.md](./quickstart.md); rules from `.specify/memory/constitution.md` (v1.0.0)

**Tests**: **Mandatory** (Constitution principle III). Inside every story, the failing tests are written first, then the code that makes them pass. Every invariant INV-001 to INV-006 must end up with at least one automated test, run on a real PostgreSQL `_test` database.

**Organization**: Tasks are grouped by user story. The backend is built first (its invariants are the assessed core); the frontend follows once the backend invariants pass.

## Format: `- [ ] [ID] [P?] [Story?] Description with file path`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story from `spec.md` (US1 to US8); shared Setup, Foundational, Polish tasks have none
- Paths are from the repository root. Backend code is under `backend/src/app/`; tests under `backend/tests/{unit,integration,api}/`; frontend under `frontend/src/`.

## Commit order (Constitution principle II)

Nothing under `backend/` or `frontend/` (except their `CLAUDE.md`) is committed until `specs/001-docs-studio/spec.md`, `plan.md` and `tasks.md` are committed. The files that already exist there (`backend/db-automation-apply/`, the Dockerfiles, the `cloudbuild.yaml` files), together with the root `compose.yaml` and `.env.example`, are committed **after** the specification, together with the first implementation work.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: project skeletons, the spec-first check and the single-command entry points

- [X] T001 Create the root `Makefile` with the targets `setup` (install backend and frontend dependencies, start the Compose databases with `docker compose up -d db db-test` unless `DATABASE_URL` points elsewhere, and apply the schema to the development database), `dev` (start the API and the web app), `test` (start `db-test`, then run the backend tests, `check-api`, and the frontend type check, lint and Vitest), `test-docker` (run the backend tests inside a container with `docker compose --profile test run --rm test`, so a machine with only Docker can run them), `check-api` and `check-spec-first`; each target delegates to uv in `backend/` or pnpm in `frontend/` (the frontend steps are skipped until the frontend skeleton exists in Phase 11)
- [X] T002 Create `scripts/check-spec-first.sh`: run `git log --reverse --diff-filter=A --name-only --format='commit %h' -- specs/001-docs-studio/spec.md backend frontend ':(exclude)backend/CLAUDE.md' ':(exclude)frontend/CLAUDE.md'` and exit non-zero unless `specs/001-docs-studio/spec.md` appears before any file under `backend/` or `frontend/`; print a clear message either way; make it executable and wire it to `make check-spec-first`
- [X] T003 [P] Create the root `compose.yaml` with `db` (PostgreSQL 17, port 5432, a named volume, a health check; the development database) and `db-test` (profile `test`, port 5433; the test database, its name ending in `_test`), and the root `.env.example` with local-only values: `ENV=local`, `BASIC_AUTH_ENABLED=false` (so a local run needs no sign-in), empty `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD`, and a placeholder `POSTGRES_PASSWORD` (no real credential is ever committed)
- [X] T004 [P] Create the backend skeleton in `backend/pyproject.toml` (Python 3.12; FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg, Alembic, uvicorn; dev: pytest, pytest-asyncio, httpx, ruff, mypy; `asyncio_mode = "auto"`, `testpaths = ["tests"]`) and the empty package folders `backend/src/app/{core,db,api/v1/routes,domains/articles}/` and `backend/tests/{unit,integration,api}/`
- [X] T005 [P] Create `backend/.env.example` listing `ENV`, `DATABASE_URL`, `TEST_DATABASE_URL`, `BASIC_AUTH_ENABLED`, `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD` with placeholder values only (no real credential)
- [X] T006 Wire Alembic in `backend/alembic.ini` and `backend/alembic/env.py` (async engine from `DATABASE_URL`) and create revision `backend/alembic/versions/0001_schema.py` whose `upgrade()` executes the whole of `backend/db-automation-apply/001_schema.sql` through the driver's simple-query path (for example the raw asyncpg connection's `execute`), because a prepared statement cannot hold several commands and the file contains functions and triggers; then confirm on a real PostgreSQL that the schema applies and whose `downgrade()` drops the tables, functions and triggers it created; an applied SQL file is never edited
- [X] T007 Create `backend/src/app/core/config.py` (pydantic-settings): `ENV`, `DATABASE_URL`, `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD`; add `BASIC_AUTH_ENABLED`; raise at start-up if authentication is enabled and either credential is empty, and in production also if authentication is not enabled; log a clear warning at start-up when authentication is off (the tests for this are in US8)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the safety net and shared plumbing that every story needs

**⚠️ CRITICAL**: no user story work begins until this phase is complete

- [X] T008 [P] Write the failing unit test `backend/tests/unit/test_test_db_guard.py`: the guard aborts, before any statement, unless the database name ends in `_test` and the host is `localhost` or `127.0.0.1` (a `/cloudsql` socket path and a production-looking name must be refused)
- [X] T009 Implement the guard and the shared fixtures in `backend/tests/conftest.py`: read `TEST_DATABASE_URL` (never `DATABASE_URL`), run the guard first, apply the schema through Alembic once per session, reset the data before each test with `BEGIN; SET LOCAL docs.allow_reset = 'on'; TRUNCATE articles, article_versions RESTART IDENTITY; COMMIT` (both tables in one statement because they reference each other, and the snapshot table's `TRUNCATE` guard allows it only with that setting), and provide a factory for **separate** database connections (pool of at least 2) for the concurrency tests
- [X] T010 [P] Create `backend/src/app/db/session.py`: async engine with `pool_size=3`, `max_overflow=2`, `pool_pre_ping=True`, `pool_recycle=1800`, lazy connection at start-up, `expire_on_commit=False`, session time zone UTC, and `SET LOCAL lock_timeout = '3s'` available to the service
- [X] T011 [P] Create `backend/src/app/core/errors.py`: the `AppError` subclasses and exception handlers producing `{ "error": { "code", "message", "details" } }`, with codes `unauthorized`, `not_found`, `validation_error`, `version_conflict`, `empty_content`, `not_published`, `version_is_live`, `slug_conflict`; replace FastAPI's default 422 body with this envelope; `version_conflict` carries `details.current_draft_version`
- [X] T012 [P] Create `backend/src/app/core/security.py`: the `require_basic_auth` dependency (credentials from settings; compare as UTF-8 bytes with `secrets.compare_digest`, both fields without short-circuiting; on failure raise the `unauthorized` error with `WWW-Authenticate: Basic realm="studio"`; never log the `Authorization` header; when `BASIC_AUTH_ENABLED` is false the dependency lets the request through, and it is an explicit setting, never an implicit fallback)
- [X] T013 [P] Write the schema-constraint tests in `backend/tests/integration/test_schema_constraints.py`: a raw `UPDATE` on `article_versions` is rejected (trigger); `TRUNCATE article_versions` is rejected unless `docs.allow_reset` is `on` in the same transaction (only the test fixture sets it); `status='published'` with a NULL pointer or NULL `published_at` is rejected (CHECK); a published article cannot return to `draft`, cannot clear the pointer or `published_at`, cannot move the pointer to a lower version number, and its slug cannot change (guard trigger); a pointer to another article's version is rejected and deleting the pointed-at version is rejected (composite foreign key)
- [X] T014 [P] Write the failing route-sweep test `backend/tests/api/test_auth_route_sweep.py`: with authentication enabled (the fixture turns `BASIC_AUTH_ENABLED` on), walk `app.routes` and fail if any route outside `/api/v1/public` and `/healthz` answers without credentials with anything other than 401
- [X] T015 Create `backend/src/app/main.py` with `create_app()`: a **writer** router with `dependencies=[Depends(require_basic_auth)]` for the whole router, a **public** router with none, `GET /healthz` (no database access), the exception handlers from T011, no CORS middleware, `Cache-Control: no-store` on writer responses, a request-ID and JSON logging setup, and `docs_url`, `redoc_url` and `openapi_url` disabled when `ENV` is `prod`; set `operation_id` **explicitly** on every route to the camelCase name used in `specs/001-docs-studio/contracts/openapi.yaml` (for example `createArticle`, `publishArticle`)
- [X] T016 [P] Create `backend/scripts/export_openapi.py`: build the app and write `backend/openapi.json` **without** a database connection
- [X] T017 Update the `Makefile` so `check-api` runs the export script, runs `pnpm gen:api` in `frontend/`, (skipping the frontend part while `frontend/` has no skeleton yet) and fails if `backend/openapi.json` or `frontend/src/lib/api/generated/` differ from what is committed

**Checkpoint**: the guard test, the constraint tests and the sweep test run; the constraint tests pass against the schema from T006

---

## Phase 3: User Story 1 - Create and edit a draft (Priority: P1) 🎯 MVP

**Goal**: a writer creates, edits and lists articles; slugs follow the rules; a taken slug gets a number.

**Independent Test**: create an article, edit it twice, list it; the public side shows nothing (quickstart scenario 1).

### Tests for User Story 1 (write first; they must FAIL before the code) ⚠️

- [X] T018 [P] [US1] Write `backend/tests/unit/test_validation.py`: title 1 to 200 characters and not only whitespace; slug matches `^[a-z0-9]+(-[a-z0-9]+)*$` and is at most 100 characters; at most 10 tags of 1 to 30 characters each, trimmed, lowercased, duplicates dropped with order kept; body at most 100,000 characters and allowed to be empty in a draft
- [X] T019 [P] [US1] Write `backend/tests/api/test_articles_create_edit_list.py`: create returns 201 with `Location` and `draft_version` 1, status `draft`, no snapshot; invalid input returns 422 `validation_error` and changes nothing; PATCH is partial (omitted fields keep their value, `tags` replaces the list); PATCH containing `slug` returns 422; PATCH needs `expected_draft_version`; a successful edit raises `draft_version` by 1; the writer list is newest `updated_at` first (ties by `id` descending), at most 100, filterable by `status`, and an unknown `status` returns 422; every route returns 401 before 404 or 422
- [X] T020 [P] [US1] Write `backend/tests/integration/test_slug_collision.py`: a taken slug gets `-2`, then `-3` (the smallest free number) and the response shows the stored slug; the base is shortened so the result stays within 100 characters; two concurrent creates with one slug (separate connections) end up with two different slugs and never a 500; the slug cannot change afterwards

### Implementation for User Story 1

- [X] T021 [P] [US1] Create `backend/src/app/domains/articles/models.py`: `Article` and `ArticleVersion` mapped to `backend/db-automation-apply/001_schema.sql` (no `create_all`); `status` limited to `draft`, `published`, `unpublished`
- [X] T022 [P] [US1] Create `backend/src/app/domains/articles/schemas.py` with `ArticleCreate`, `ArticleUpdate` (unknown fields forbidden, `expected_draft_version` required, no slug), `ArticleSummary`, `ArticleDetail`, quoting the constraints verbatim: title "1 to 200 characters after trimming"; slug "`^[a-z0-9]+(-[a-z0-9]+)*$`, 1 to 100 characters"; body "at most 100,000 characters; may be empty in a draft"; tags "at most 10 items; each 1 to 30 characters, trimmed, lowercased, no duplicates (order kept)"; `draft_version` "starts at 1, never below 1"
- [X] T023 [US1] Create `backend/src/app/domains/articles/repository.py` (thin): insert an article, fetch by id, list with filter/limit/offset, find taken slugs for a base, and the conditional draft update `UPDATE … WHERE id=:id AND draft_version=:expected RETURNING draft_version`
- [X] T024 [US1] Create `backend/src/app/domains/articles/service.py` with `create_article` (smallest free numeric suffix; on SQLSTATE 23505 retry up to 5 times; `409 slug_conflict` only if every attempt loses) and `get_article`
- [X] T025 [US1] Extend `backend/src/app/domains/articles/service.py` with `update_draft` (0 rows: a follow-up `SELECT draft_version` gives 404 when the article is missing, otherwise `409 version_conflict` with the current version) and `list_articles`; the service owns the transaction (`async with session.begin()`) and is the only layer that commits
- [X] T026 [US1] Create `backend/src/app/api/v1/routes/articles.py` (the writer router) with `createArticle`, `listArticles`, `getArticle`, `updateArticle` and every error response declared; register it in `backend/src/app/main.py`; all T018 to T020 tests pass

**Checkpoint**: User Story 1 works and is tested on its own

---

## Phase 4: User Story 2 - Publish a draft as an immutable snapshot (Priority: P1)

**Goal**: publish is atomic, creates the next numbered snapshot, and sets `published_at` only the first time.

**Independent Test**: publish, edit, publish again; check version numbers, the live snapshot and the unchanged `published_at` (quickstart scenarios 2 and 3).

### Tests for User Story 2 (write first) ⚠️

- [X] T027 [P] [US2] Write `backend/tests/integration/test_publish_lifecycle.py`: the first publish creates version 1, status `published`, the pointer and `published_at`; the next publish creates version 2, moves the pointer and keeps `published_at`; `draft_version` rises by 1 per snapshot-creating publish; numbering comes from `last_version_number`; an empty title or body returns 422 `empty_content` and creates nothing; a missing article returns 404
- [X] T028 [P] [US2] Write `backend/tests/integration/test_publish_atomicity.py`: parametrize a failure (by patching the repository functions) after each step of Publish (after the lock, after the counter update, after the insert, after the status update); after every failure the article row (status, pointer, `published_at`, `draft_version`, `last_version_number`) and the list of snapshots are identical to before
- [X] T029 [P] [US2] Write `backend/tests/integration/test_publish_concurrency.py`: with `asyncio.gather` on separate connections, two publishes with the same `expected_draft_version` give exactly one 201 and one 409, no 5xx, contiguous version numbers and a pointer at the newest version; repeat with five concurrent publishes

### Implementation for User Story 2

- [X] T030 [US2] Add `PublishResult` and `ExpectedVersion` to `backend/src/app/domains/articles/schemas.py`
- [X] T031 [US2] Add the Publish SQL to `backend/src/app/domains/articles/repository.py`: `SELECT … FOR UPDATE OF a` with a `LEFT JOIN` to the live snapshot, the `last_version_number` increment `RETURNING`, the snapshot insert from the draft, and the final update using `COALESCE(published_at, clock_timestamp())` and `draft_version + 1`
- [X] T032 [US2] Add `publish_article` to `backend/src/app/domains/articles/service.py` in this order inside one transaction: lock (404), `expected_draft_version` (409 `version_conflict`), non-empty title and body (422 `empty_content`), create the snapshot and update the article (the idempotent branch is added in US7); use `SET LOCAL lock_timeout`
- [X] T033 [US2] Add the `publishArticle` route to `backend/src/app/api/v1/routes/articles.py` (201 with `PublishResult`), with its error responses declared; T027 to T029 pass

**Checkpoint**: Publish is atomic and race-safe

---

## Phase 5: User Story 3 - Readers see only published content (Priority: P1)

**Goal**: public list and detail come from the live snapshot only; every kind of "not found" looks identical.

**Independent Test**: publish, then edit the draft without publishing; the public page still shows the published text; never-published, taken-down and made-up slugs return the same 404 (quickstart scenarios 2 and 4).

### Tests for User Story 3 (write first) ⚠️

- [X] T034 [P] [US3] Write `backend/tests/api/test_public_read.py`: the list shows only published articles, newest `published_at` first (ties by `id` descending), with title, tags and `published_at`, and `updated_at` null until the live version number is 2 or more; an empty list returns `[]`; the detail shows the live snapshot's title, tags and body, never the draft, even after the draft is edited; a never-published article, an unpublished article, a missing slug and a malformed slug all return the same 404 status and the same body; `limit` above 100 returns 422
- [X] T035 [P] [US3] Write `backend/tests/api/test_public_allow_list.py`: a public response contains only `slug`, `title`, `tags`, `body` (detail only), `published_at`, `updated_at` or `live_created_at`; it never contains `draft_*`, `draft_version`, `articles.updated_at`, `status` or an internal id; no long-lived `Cache-Control` header is sent; public routes accept requests with and without an `Authorization` header

### Implementation for User Story 3

- [X] T036 [US3] Add `PublicArticleListItem` and `PublicArticle` to `backend/src/app/domains/articles/schemas.py` (the allow-list: nothing else is serialized)
- [X] T037 [US3] Add the public queries to `backend/src/app/domains/articles/repository.py`: each read is **one** statement joining `articles` to `article_versions` on `current_published_version_id` with `status = 'published'`, selecting only title, tags, dates (and body for the detail), so title and body always come from the same version
- [X] T038 [US3] Create `backend/src/app/api/v1/routes/public.py` (the public router, no auth dependency) with `listPublicArticles` (`limit` default 20, maximum 100, `offset`) and `getPublicArticle` (identical 404 for every kind of miss); register it in `backend/src/app/main.py`; T034 and T035 pass

**Checkpoint**: Stories 1 to 3 give a working create, publish and read loop (suggested MVP)

---

## Phase 6: User Story 4 - Unpublish without losing history (Priority: P1)

**Goal**: unpublish changes only the status and keeps every snapshot, the pointer and `published_at`.

**Independent Test**: publish, unpublish, check the public 404 and the intact history, publish again (quickstart scenario 4).

### Tests for User Story 4 (write first) ⚠️

- [X] T039 [P] [US4] Write `backend/tests/integration/test_unpublish.py`: unpublish sets `unpublished` and changes nothing else (snapshots, pointer, `published_at`, draft, `draft_version`); the public detail then returns 404; unpublishing an article that is not `published` returns 409 `not_published` and changes nothing; republishing after an edit creates a new snapshot and keeps the original `published_at`
- [X] T040 [P] [US4] Write `backend/tests/integration/test_unpublish_publish_race.py`: simultaneous Unpublish and Publish on separate connections serialize on the row lock and either order leaves a valid state with no 5xx

### Implementation for User Story 4

- [X] T041 [US4] Add `unpublish_article` to `backend/src/app/domains/articles/service.py` (take the row lock, `status <> 'published'` gives 409 `not_published`, otherwise `UPDATE articles SET status = 'unpublished'`; no `expected_draft_version`; no `draft_version` change)
- [X] T042 [US4] Add the `unpublishArticle` route to `backend/src/app/api/v1/routes/articles.py`; T039 and T040 pass

**Checkpoint**: Stories 1 to 4 work together

---

## Phase 7: User Story 5 - Version history, restore and safe deletion (Priority: P1)

**Goal**: list and open snapshots, restore into the draft without touching history, and delete only unprotected snapshots.

**Independent Test**: publish three versions, restore the first, try to delete the live one (refused), delete an older one (quickstart scenarios 5 and 6).

### Tests for User Story 5 (write first) ⚠️

- [X] T043 [P] [US5] Write `backend/tests/api/test_versions_history.py`: the history is newest first with `id`, `version_number`, `title`, `created_at` and `is_live`, and without the body; opening a version shows its full title, body and tags; a version number the article does not have returns 404
- [X] T044 [P] [US5] Write `backend/tests/integration/test_restore.py`: Restore replaces only the draft's title, body and tags and raises `draft_version` by 1; for an article that is never published, published and unpublished, **every column of every row** of `article_versions` for the article, plus `status`, the pointer and `published_at`, is identical before and after; nothing is published; the slug is untouched; a missing version number returns 404 and changes nothing
- [X] T045 [P] [US5] Write `backend/tests/integration/test_delete_version.py`: deleting the live version returns 409 `version_is_live` and the row remains; after Unpublish it is still refused; after a republish an older version deletes with 204; a missing number returns 404; a number is never reused (the next publish after a deletion gets the next unused number); a foreign-key violation is mapped to the same 409
- [X] T046 [P] [US5] Write `backend/tests/integration/test_delete_publish_race.py`: Delete racing Publish on separate connections never returns 5xx and never leaves the pointer dangling

### Implementation for User Story 5

- [X] T047 [US5] Add `VersionSummary` and `VersionDetail` to `backend/src/app/domains/articles/schemas.py`
- [X] T048 [US5] Add to `backend/src/app/domains/articles/repository.py`: the history query (no body, `is_live` from the pointer), the single-version query, Restore as **one** statement (`UPDATE articles SET draft_title=v.title, draft_body=v.body, draft_tags=v.tags, draft_version=draft_version+1 FROM article_versions v WHERE articles.id=:id AND v.article_id=:id AND v.version_number=:n AND articles.draft_version=:expected RETURNING articles.draft_version`) and the version delete
- [X] T049 [US5] Add to `backend/src/app/domains/articles/service.py`: `list_versions`, `get_version`, `restore_version` (0 rows: 404 if the article or version is missing, otherwise 409; never touches status, pointer or `published_at`) and `delete_version` (takes the **same row lock** as Publish, reads the pointer, 404 for a missing number, 409 `version_is_live` for the protected version, otherwise delete; map SQLSTATE 23503 to the same 409)
- [X] T050 [US5] Add the `listVersions`, `getVersion`, `restoreVersion` and `deleteVersion` routes to `backend/src/app/api/v1/routes/articles.py`; T043 to T046 pass

**Checkpoint**: the history, Restore and Delete rules hold, including under races

---

## Phase 8: User Story 6 - Detect conflicting edits (Priority: P1)

**Goal**: any change based on a stale draft version is refused with a clear conflict and changes nothing.

**Independent Test**: save from two stale views; the second is refused and nothing is overwritten (quickstart scenario 7).

### Tests for User Story 6 (write first) ⚠️

- [X] T051 [P] [US6] Write `backend/tests/integration/test_optimistic_concurrency.py`: a stale edit returns 409 `version_conflict` with `details.current_draft_version`, changes nothing and does not overwrite the newer edit; an edit and a Restore sent with the same `expected_draft_version` give exactly one success; a Publish whose `expected_draft_version` is older than a committed edit returns 409 and creates no snapshot
- [X] T052 [P] [US6] Write `backend/tests/integration/test_draft_version_semantics.py`: `draft_version` rises by exactly 1 on each successful edit, Restore and snapshot-creating Publish, and does not change on Unpublish, on deleting a version, or on a publish that creates nothing
- [X] T053 [P] [US6] Write `backend/tests/api/test_check_order.py`: for each writer route the order is authentication (401), existence (404), input shape (422), `expected_draft_version` (409), business rules (for example `empty_content`, `not_published`)

### Implementation for User Story 6

- [X] T054 [US6] Fix whatever T051 to T053 expose in `backend/src/app/domains/articles/service.py` and `backend/src/app/core/errors.py` so the order of checks and the conflict details are identical on every route; all three tests pass

**Checkpoint**: INV-005 is verified across edit, Restore and Publish

---

## Phase 9: User Story 7 - Publishing the same content twice creates no duplicate (Priority: P2)

**Goal**: Idempotent Publish compares only with the live snapshot.

**Independent Test**: publish twice with no change, then unpublish and publish with no change (quickstart scenario 8).

### Tests for User Story 7 (write first) ⚠️

- [X] T055 [P] [US7] Write `backend/tests/integration/test_idempotent_publish.py`: an unchanged draft returns 200 with `created: false`, creates no snapshot and leaves `published_at`, the pointer and `draft_version` unchanged; for an unpublished article with an unchanged draft it returns to `published` with no new snapshot; a draft equal to an **older** (not live) version still creates a new snapshot; a stale `expected_draft_version` still returns 409 before the idempotent check, and an empty title or body returns 422 before it

### Implementation for User Story 7

- [X] T056 [US7] Add the idempotent branch to `publish_article` in `backend/src/app/domains/articles/service.py`: after the 409 and 422 checks, compare the draft's title, body and tags with the live snapshot only (`IS NOT DISTINCT FROM`, tags as an ordered list); if equal, create nothing and, when the status was `unpublished`, set it back to `published`
- [X] T057 [US7] Make `PublishResult.created` and the HTTP status (200 versus 201) follow the outcome in `backend/src/app/api/v1/routes/articles.py`; T055 passes

**Checkpoint**: the adopted optional feature works

---

## Phase 10: User Story 8 - Writer area is protected (Priority: P2)

**Goal**: every writer operation needs the credentials; public operations never do.

**Independent Test**: call every writer route with none, wrong and right credentials (quickstart scenario 9).

### Tests for User Story 8 (write first) ⚠️

- [X] T058 [P] [US8] Write `backend/tests/api/test_basic_auth_matrix.py`: with authentication enabled, every writer route with no, wrong and right credentials (401 with `WWW-Authenticate: Basic` for the first two, even for an article that does not exist; success for the right ones); credentials with non-ASCII characters do not cause a 500; a public route with a stray `Authorization` header still works; writer responses carry `Cache-Control: no-store`
- [X] T059 [P] [US8] Write `backend/tests/api/test_production_hardening.py`: with `ENV=prod` the app refuses to start unless `BASIC_AUTH_ENABLED` is true and both credentials are non-empty; with authentication enabled and either credential empty it refuses to start in any environment; with `ENV=local` and `BASIC_AUTH_ENABLED=false` the writer routes work with no credentials and a warning is logged; `/docs`, `/redoc` and `/openapi.json` return 404 in production; no CORS headers are sent; the `Authorization` header and the credentials never appear in captured logs

### Implementation for User Story 8

- [X] T060 [US8] Make T058 and T059 pass by hardening `backend/src/app/core/security.py`, `backend/src/app/core/config.py` and `backend/src/app/main.py` (production start-up refusal, documentation endpoints off in production, UTF-8 byte comparison, `no-store`, no credential logging); the route-sweep test from T014 also passes

**Checkpoint**: the backend is complete. All six invariants (INV-001 to INV-006) have passing tests.

---

## Phase 11: Frontend (after the backend invariants pass)

**Purpose**: the minimal UI: public pages and the writer area. Story labels show which story each screen serves.

- [X] T061 [P] Create the frontend skeleton in `frontend/package.json` (Next.js 16, React 19, TypeScript, `openapi-fetch`, `openapi-typescript`, Zod, Tailwind CSS (the current major version, confirmed at setup) with its PostCSS setup in `frontend/postcss.config.mjs` and the entry stylesheet `frontend/src/app/globals.css`, `react-markdown`, `rehype-sanitize`, Vitest; scripts `dev`, `build`, `lint`, `typecheck`, `test`, `gen:api`), `frontend/tsconfig.json` (`strict` and `noUncheckedIndexedAccess` on), `frontend/next.config.ts` (`output: "standalone"`), `frontend/eslint.config.mjs`, `frontend/vitest.config.ts`, and an empty `frontend/public/.gitkeep`
- [X] T062 [P] Create `frontend/.env.example` listing `API_BASE_URL` and `BASIC_AUTH_ENABLED` (a runtime-only server variable, never `NEXT_PUBLIC_*`)
- [X] T063 Generate `backend/openapi.json` (`backend/scripts/export_openapi.py`) and the frontend types into `frontend/src/lib/api/generated/` (`pnpm gen:api`); `make check-api` passes; never edit the generated files by hand
- [X] T064 [P] Create `frontend/src/lib/env.ts` that validates `API_BASE_URL` **lazily** (inside the client factory) so `next build` needs no API
- [X] T065 [P] Create the base layout and design tokens in `frontend/src/app/layout.tsx` and `frontend/src/app/globals.css` (Tailwind entry): a neutral palette with one accent colour, a system font stack, generous whitespace, a centred readable content width, light theme only
- [X] T066 [P] Create the small shared UI components in `frontend/src/components/ui/` (`button.tsx`, `input.tsx`, `textarea.tsx`, `tag.tsx`, `status-badge.tsx`, `empty-state.tsx`), Tailwind classes only, no component library, with a visible keyboard focus on every interactive element
- [X] T067 [P] [US3] Write the failing Vitest file `frontend/tests/markdown.test.ts`: a `javascript:` link is removed, a raw `<script>` is not rendered, `http`, `https` and `mailto` links are kept, plain Markdown renders
- [X] T068 [US3] Create `frontend/src/lib/markdown.ts`: the one renderer and sanitizer (`react-markdown` with `rehype-sanitize`, no raw HTML, links limited to `http`, `https`, `mailto`) used by both the public page and the preview; T067 passes
- [X] T069 [US8] Create `frontend/src/lib/api/server-client.ts`: an `openapi-fetch` client that takes the `Authorization` header **per call** (it is simply absent when authentication is off) (read with `headers()` in the caller), never from a module-level singleton, with `cache: "no-store"`
- [X] T070 [P] [US8] Create `frontend/src/app/auth/challenge/route.ts`: a route handler returning `401` with `WWW-Authenticate: Basic realm="studio"` (a Server Action cannot set that header)
- [X] T071 [P] [US8] Create `frontend/src/proxy.ts`: when `BASIC_AUTH_ENABLED` is true, on `/studio/**` requests only check that an `Authorization` header is present and otherwise answer `401` with `WWW-Authenticate: Basic realm="studio"` on that same address (a redirect to `/auth/challenge` would loop, because browsers send saved credentials only to the path that challenged them); FastAPI remains the only validator
- [X] T072 [US3] Create `frontend/src/app/(public)/docs/page.tsx` with `export const dynamic = "force-dynamic"`: the public list (title, tags, publication date, and the updated date when present) with a friendly empty state
- [X] T073 [P] [US3] Create `frontend/src/app/(public)/docs/[slug]/page.tsx` with `export const dynamic = "force-dynamic"`: render the live snapshot through `lib/markdown.ts`, call `notFound()` on a 404 (a real 404 status), and `generateMetadata` from the snapshot
- [X] T074 [US1] Create `frontend/src/app/(studio)/studio/page.tsx`: the writer's article list with a create form and a friendly empty state; mark `/studio` as `noindex`
- [X] T075 [US1] Create `frontend/src/features/articles/editor-form.tsx` (Client Component, `useActionState`): title, body, tags, a live Markdown preview from `lib/markdown.ts`, saving with the `draft_version` the form was **loaded with**
- [X] T076 [US6] Create `frontend/src/features/articles/conflict-view.tsx`: on `version_conflict` keep the writer's unsent input, show that the server copy changed, and offer "reload the latest" or "resubmit against the new version"
- [X] T077 [US5] Create `frontend/src/features/articles/history-panel.tsx`: the version list (newest first, live one marked), open a version, Restore, Delete (the button is also refused by the API for the protected version, and the screen shows that message)
- [X] T078 [US1] Create `frontend/src/app/(studio)/studio/[id]/page.tsx` combining the editor, Publish and Unpublish buttons, the history panel and the conflict view
- [X] T079 [US1] Create `frontend/src/app/(studio)/studio/actions.ts` (Server Actions: create, update, publish, unpublish, restore, delete): read the incoming `Authorization` header with `headers()` and pass it on every API call, return the new `draft_version` after Publish and Restore, surface a 401 so the page redirects to `/auth/challenge`, and return the current version on a 409 without discarding input
- [X] T080 [US8] Add the security headers to `frontend/next.config.ts` (`Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`, HSTS) and confirm no CORS is enabled
- [X] T081 Do a **time-boxed** Tailwind polish pass over every screen (public list, public article, writer list, editor with preview, history panel, conflict view): consistent spacing and typography, readable on phone and desktop widths, friendly empty and error states, readable contrast; stop when the time box ends, because looks are not assessed (FR-038)
- [X] T082 Make `pnpm typecheck`, `pnpm lint` and `pnpm test` pass in `frontend/` and confirm `make test` runs them

**Checkpoint**: all scenarios in `quickstart.md` can be done in the browser

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: the final checks and the deliverables

- [X] T083 [P] Write `backend/tests/api/test_contract_matches_openapi.py`: the generated `backend/openapi.json` has the same paths, methods, `operationId`s and response status codes as `specs/001-docs-studio/contracts/openapi.yaml`
- [X] T084 Run `make test` on a clean checkout and fix anything that fails; it must be one command that runs the backend tests, the OpenAPI drift check and the frontend checks, and every invariant (INV-001 to INV-006) must have at least one passing test
- [X] T085 Run every scenario in `specs/001-docs-studio/quickstart.md` (1 to 10) locally and record the results in `specs/001-docs-studio/quickstart-results.md` (scenario, expected, observed, pass or fail), and time scenario 1 plus a first publish by hand to check that it takes under 3 minutes (SC-009)
- [X] T086 Extend `compose.yaml` with `migrate` (the backend image running `alembic upgrade head` once `db` is healthy), `backend` (port 8000, started after `migrate` completes) and `frontend` (port 3000, `API_BASE_URL=http://backend:8000`), built from `backend/Dockerfile` and `frontend/Dockerfile`; fix the Dockerfiles as needed (pin the uv image by digest, `UV_NO_CACHE=1`, `UV_PYTHON_DOWNLOADS=never`, `--proxy-headers`, honour `$PORT`, `COPY --chown=app` in the frontend). This is **not** low priority: it is part of the short setup command
- [X] T087 Add a `test` service (profile `test`) to `compose.yaml` that builds the backend image with its dev dependencies and runs the whole backend test suite against `db-test` (`docker compose --profile test run --rm test`), make `make test-docker` call it, and confirm on a machine with only Docker that it passes; this is how an assessor with only Docker runs the tests with one command
- [X] T088 On a clean checkout with only Docker installed, run `cp .env.example .env` and `docker compose up --build`, open the web app on port 3000, and run `quickstart.md` scenarios 1 to 10; record the result in `specs/001-docs-studio/quickstart-results.md`
- [X] T089 Finish `README.md`: update every row of the features table to its real status and, for anything not done, how it would be built; replace the "(planned)" notes with what was actually run; keep the assessor path and the design trade-offs paragraph
- [X] T090 Update `docs/requirements.md`, `docs/nextjs-fastapi-architecture.html` and their Japanese versions in `docs/ja/` for any design change made during implementation, and confirm the two languages have the same files and the same rows (`ls docs docs/ja`); also confirm that nothing outside `docs/ja/` contains Japanese (comments in code and configuration files, the `CLAUDE.md` files, the specs and the README): `grep -rlP "[\x{3040}-\x{30ff}\x{4e00}-\x{9fff}]" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=ja .` must print nothing
- [X] T091 Run `scripts/check-spec-first.sh` and confirm it passes (the specification was committed before any file under `backend/` or `frontend/`), and re-check the Constitution Check in `plan.md`

### Low priority, last (do not let these delay anything above)

- [X] T092 Update `backend/cloudbuild.yaml` and `frontend/cloudbuild.yaml`: set `ENV=prod` and `BASIC_AUTH_ENABLED=true` in the environment, add `--max-instances`, `--cpu-boost` and `--min-instances=0`; make the migration Job use `--max-retries=0` and a task timeout; use `--set-cloudsql-instances`; add a first step that fails fast if `_SQL_INSTANCE` or `_RUNTIME_SA` is empty
- [X] T093 Build the images through Cloud Build (the Dockerfiles have already been built by Docker Compose) and fix anything that only fails there; until this has been run, never describe the Cloud Run deployment as verified
- [X] T094 Create by hand the Cloud SQL instance (with the development, test and production databases kept separate), the Artifact Registry repository, the Secret Manager secrets (`database-url`, `basic-auth-user`, `basic-auth-password`) and the service accounts with the roles listed in `docs/requirements.md` section 12
- [X] T095 Deploy both services with `gcloud builds submit backend --config backend/cloudbuild.yaml` and `gcloud builds submit frontend --config frontend/cloudbuild.yaml`, run `quickstart.md` scenarios 1 to 10 on the deployed site, and put the URL at the top of `README.md` (credentials are shared outside the repository)

---

## Phase 13: Amendments after implementation (done)

**Purpose**: bring the task list in line with changes agreed after implementation started (`spec.md`, "Amendments", A-1 to A-6). All of these are built and checked; they are listed so the history of the work is complete.

- [X] T096 [US1] (A-1) Replace the "create" form with writing directly in the editor: `frontend/src/features/articles/new-article-form.tsx`, `frontend/src/app/(studio)/studio/new/page.tsx`, the `createArticleDirect` Server Action, and a "New article" button on the writer list; remove `create-form.tsx`. Nothing exists until the first save
- [X] T097 [US1] (A-1) Slug field that holds only the slug; `stripAddress` and `slugForNewArticle` (title, else generated) in `frontend/src/lib/format.ts`, tested in `frontend/tests/format.test.ts`
- [X] T098 [US2] (A-2) "Save & publish" in `frontend/src/features/articles/article-workspace.tsx` (save, then publish the saved version; say so if only the publish failed) and on the new-article form. Checked in a real browser: new article → Save & publish → public; edit → Save & publish → version 2
- [X] T099 (A-3) One content width on every page (the two `layout.tsx` files; shorter line length for the article body)
- [X] T100 (A-4) `_tidy_openapi` in `backend/src/app/main.py` and the 422 entries in `contracts/openapi.yaml`, found by `backend/tests/api/test_contract_matches_openapi.py` (T083)
- [X] T101 (A-5) `TEST_DATABASE_EXTRA_HOSTS` in `backend/tests/db_guard.py` and `backend/tests/conftest.py`, set for the `test` service in `compose.yaml`; unit tests in `test_test_db_guard.py`
- [X] T102 (A-6) `frontend/src/proxy.ts` answers the sign-in challenge on the requested address
- [X] T103 Update `quickstart.md` (scenario 11) and `quickstart-results.md` for A-1 and A-2

- [X] T104 (A-7) Settings and wiring: `AI_ENABLED`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`), output and rate limits in `backend/src/app/core/config.py` (on without a key is a start-up error), the `anthropic` dependency, `.env.example` and `compose.yaml` pass-through; AI stays off by default
- [X] T105 [P] (A-7) Write the failing tests first: `backend/tests/api/test_ai_draft.py` (off by default and "not available"; status; 401 before anything; a body is streamed from the title and tags in several pieces and no article or snapshot is created; empty and over-long input refused with no model call; rate limit 429; model failure, refusal and unusable reply give a generic 502; nothing logged) and `backend/tests/unit/test_ai_generator.py` (the request has the configured model, the token cap, no prefill and no sampling parameters; the text arrives piece by piece; refusals, cut-off and SDK errors become generic failures). A fake client is injected; no test uses the network
- [X] T106 (A-7) Implement `backend/src/app/domains/ai/` (generator, rate limiter), `backend/src/app/api/v1/routes/ai.py` (`getAiStatus`, `generateDraft`), the error codes `ai_disabled`, `ai_unavailable` and `rate_limited`, and the contract entries in `contracts/openapi.yaml`; T105 passes and the contract test passes
- [X] T107 (A-7) Frontend: Server Action `generateAiDraft`, and `ai-generate-bar.tsx`: one "Generate with AI" button above the body field in the new-article form and the editor, always visible (disabled with a note when the feature is off); it sends the title, tags and body as notes, fills the body as the text streams in (Stop keeps what has arrived), never changes the title or tags, and labels the result as AI output
- [X] T108 (A-8) Make the preview follow the text with `useDeferredValue` in `editor-form.tsx` and `new-article-form.tsx`
- [X] T109 (A-7) Update `quickstart.md` (scenario 12, a manual step that needs a key), `README.md`, and check the Constitution Check in `plan.md`
- [X] T110 (A-9) Stream the AI body: server-sent events from `POST /ai/draft` (`backend/src/app/api/v1/routes/ai.py`, `domains/ai/generator.py`), the pass-through route handler `frontend/src/app/(studio)/studio/ai-draft/route.ts`, and the reading and Stop logic in `ai-generate-bar.tsx`; tests first (several pieces arrive, a failure before the first piece is a normal error, a failure in the middle is an `error` event), contract and quickstart updated
- [X] T111 Real-browser tests of the screens with Playwright (`frontend/e2e/`, `frontend/playwright.config.ts`): new article (nothing created until the first save, slug behaviour, Save draft, Save & publish and a second edit), history (Live badge, View, Restore, delete with confirmation, Unpublish and Publish), the edit-conflict screen with Resubmit, the public list, detail and uniform 404, no request to another site, Body and Preview height, and the AI button state (never clicked: the AI feature is off in the test system)
- [X] T112 `compose.e2e.yaml` and `scripts/e2e.sh`, run with `make e2e`: a throwaway system (own database in tmpfs, API on 18000, web app on 13000, writer login and AI off) started before the tests and always removed afterwards, so no development data is touched; not part of `make test`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies; start immediately.
- **Foundational (Phase 2)**: needs Phase 1; it blocks every story. The guard test (T008) and its implementation (T009) come first, before any test touches a database.
- **User stories (Phases 3 to 10)**: all need Phase 2. Run them in priority order (P1 stories first, then US7 and US8); stories reuse the same files, so most work is sequential.
- **Frontend (Phase 11)**: needs the backend invariants to pass (Phases 3 to 10).
- **Polish (Phase 12)**: needs everything above. The last four tasks (T092 to T095) are low priority and must never block the rest.

### User story dependencies

- **US1** (create and edit): after Phase 2; no dependency on other stories.
- **US2** (publish): needs US1 (an article to publish).
- **US3** (public reading): needs US2 (something published to read).
- **US4** (unpublish): needs US2.
- **US5** (versions, Restore, Delete): needs US2 (snapshots to manage).
- **US6** (conflicts): needs US1, US2 and US5 (it verifies edit, Publish and Restore together).
- **US7** (idempotent publish): needs US2 and US4 (for the unpublished case).
- **US8** (writer protection): the dependency is attached from Phase 2 (T012, T015); this story only hardens and verifies it.

### Within each story

- The failing tests come first; the code then makes them pass (Constitution principle III).
- Schemas before repository, repository before service, service before routes.
- Tasks that edit the same file are not marked [P] and run in order.

### Parallel opportunities

- Setup: T003, T004 and T005 together (`compose.yaml` with `.env.example`, the backend skeleton, and `backend/.env.example`).
- Foundational: T008, T010, T011, T012, T013, T014, T016 together (different files); T009 follows T008.
- Inside a story: the test files marked [P] together (they are different files); `models.py` and `schemas.py` (T021, T022) together.
- Frontend: T061, T062, T064, T065 and T066 together (skeleton, env example, lazy env check, base layout, shared components), then T067, T070, T071 and T073 together once their prerequisites exist.

### Parallel example: User Story 2 tests

```bash
# Write these three failing tests together (different files):
Task: "Write backend/tests/integration/test_publish_lifecycle.py"
Task: "Write backend/tests/integration/test_publish_atomicity.py"
Task: "Write backend/tests/integration/test_publish_concurrency.py"
```

---

## Implementation Strategy

### Minimum viable product (assessed core)

1. Phase 1 and Phase 2 (the guard and the schema tests first).
2. Phase 3 (US1), Phase 4 (US2), Phase 5 (US3): create, publish, read.
3. **Stop and validate** with quickstart scenarios 1 to 3.

### Incremental delivery

1. Add US4 (unpublish), then US5 (history, Restore, Delete), then US6 (conflicts): each finishes with its invariant tests passing.
2. Add US7 (idempotent publish) and US8 (hardening).
3. Only then the frontend (Phase 11), then Polish.
4. The Cloud Run work (T092 to T095) is last and optional for the assessed scope.

### If time runs short

Stop adding features. Finish the invariants and their tests (Phases 3 to 10), then the README (T089): list what is not done, and how it would be built, in the features table. Do not start the low-priority deployment tasks until everything else is done.

## Notes

- [P] tasks touch different files and have no dependency on unfinished work.
- Every story is independently testable at its checkpoint.
- Excluded on purpose: Save as Version, Diff View and any caching layer. No task here builds them. (AI draft generation was excluded at first and added later as an optional extra: see amendment A-7 in `spec.md`.)
- Commit in the order given in "Commit order" above; never rewrite history.
