# Implementation Plan: Docs Studio

**Branch**: none (no git branch is created; the work lives in `specs/001-docs-studio`) | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-docs-studio/spec.md`

## Summary

Docs Studio lets a small internal team write, publish, unpublish and version articles, and lets anyone read published articles. The primary requirement is **data integrity**: a draft and published content never share a row, every publish creates an immutable numbered snapshot inside one atomic transaction, the protected (live) snapshot can never be deleted, Restore only copies into the draft, and concurrent edits are detected with an `expected_draft_version` check.

Technical approach (decided in [research.md](./research.md)): a FastAPI backend on PostgreSQL where every writer operation takes the article's row lock first and decides against the locked row; a Next.js (App Router) frontend that renders public pages dynamically and forwards the writer's Basic credentials to the API; the schema kept as numbered SQL files in `backend/db-automation-apply/` and applied by Alembic; and automated tests, run on a real PostgreSQL `_test` database, that cover every invariant. The database enforces what the application also enforces (triggers, CHECK and composite foreign key), so a bug cannot store a bad state.

Out of this plan, on purpose: AI draft generation (built later as an optional extra, see amendment A-7; it uses the Claude API on prepaid credit), Save as Version, Diff View and any caching layer.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 in strict mode on Node.js 22 (frontend)

**Primary Dependencies**: Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), asyncpg, Alembic, uvicorn. Frontend: Next.js 16 (App Router), React 19, `openapi-typescript` and `openapi-fetch` (types and client generated from the contract), Tailwind CSS (utility-first styling, the current major version, confirmed at setup), Zod (form checks), a Markdown renderer with a sanitizer (`react-markdown` with `rehype-sanitize`). Tooling: uv (Python), pnpm (Node), ruff and mypy, ESLint.

**Storage**: PostgreSQL. Production on Cloud SQL. Local runs use PostgreSQL 17 started by Docker Compose (`db` for development, `db-test` for tests), or Cloud SQL through the Auth Proxy; the target is chosen by `DATABASE_URL` and `TEST_DATABASE_URL`, and development, test and production databases are separate. The DDL is the numbered SQL in `backend/db-automation-apply/` (source of truth).

**Testing**: pytest with pytest-asyncio and httpx (`ASGITransport`) against a real PostgreSQL `_test` database (no database mocks); Vitest for the shared Markdown sanitizer; `tsc --noEmit` and ESLint for the frontend; Playwright real-browser tests of the screens (`make e2e`, against a throwaway Docker system, run separately from `make test`). One command, `make test`, runs everything including the OpenAPI drift check.

**Target Platform**: Docker Compose for the local run (only Docker is needed on the machine); Linux containers on GCP Cloud Run for deployment (low priority and not verified); developed on macOS or Linux.

**Project Type**: Web application (backend API and frontend in one repository).

**Performance Goals**: A small site: public reads are expected to be quick on this small site (this is not measured and no performance target is assessed), every list is capped at 100 items, and a publish completes in one short transaction.

**Constraints**: No caching of any kind for published content; every writer route behind Basic authentication; credentials only from environment variables; the API connection pool is small (3 plus 2 overflow) so three Cloud Run instances fit a small database; the number of instances is capped.

**Scale/Scope**: A handful of writers, up to a few thousand articles, each with a modest number of versions; 10 writer operations, 2 public operations and a health check, 4 screens (article list, editor with preview and history, public list, public article).

No `NEEDS CLARIFICATION` items remain; every open point was decided in `docs/requirements.md` (sections 11 to 13) and is recorded in [research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.* Evaluated against `.specify/memory/constitution.md` v1.0.0.

| Principle | Gate | Status (pre-design) | Status (post-design) |
|---|---|---|---|
| I. Data Integrity First | Draft and snapshots in separate tables; immutability trigger; one atomic publish; protected version undeletable; Restore copies only; `expected_draft_version` | PASS: all six rules are designed in `data-model.md` and `research.md` (R-01 to R-05) | PASS: contract declares the 409 and `version_is_live` responses; DDL enforces them |
| II. Specification Before Implementation | spec, plan and tasks exist before `backend/` and `frontend/` files are committed; `scripts/check-spec-first.sh` | PASS: this feature directory is the evidence; the script is a task | PASS: `tasks.md` orders the script first |
| III. Tests Mandatory, Before UI | Every INV has at least one test on a `_test` database; guard; `make test`; test-first | PASS: test plan in `quickstart.md` and the architecture document 12.1 | PASS: tasks place invariant tests before implementation and before the UI |
| IV. Secure by Default | Router-level Basic auth, switched by `BASIC_AUTH_ENABLED` (required in production, may be off for a local run); 401 before 404 and 422; credentials from environment; allow-list public schema; route-sweep test | PASS: R-07, R-12 | PASS: contract marks writer paths with the security scheme and public paths without |
| V. Simplicity and Scope | Core first; only Idempotent Publish and Slug collision handling; AI (optional extra, A-7), Save as Version, Diff View excluded; deployment low priority | PASS: scope list above | PASS: no excluded feature appears in the contract or the model |
| VI. Language and Documentation | Everything outside `docs/ja/` in Canadian English; `docs/ja` twins in sync | PASS | PASS: `docs/` updated whenever this plan changes the design |
| VII. No Caching | Public pages `force-dynamic`; writer `no-store`; no cache layer | PASS: R-08 | PASS: contract documents the cache headers |

**Result**: no violations, so the Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-docs-studio/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: decisions, rationale, alternatives
├── data-model.md        # Phase 1 output: entities, rules, state transitions
├── quickstart.md        # Phase 1 output: how to run and validate end to end
├── contracts/
│   └── openapi.yaml     # Phase 1 output: the writer and public API contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
├── quickstart-results.md # Results of running the quickstart (written during implementation)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
compose.yaml                     # local run: db, db-test, migrate, backend, frontend (`docker compose up --build`)
.env.example                     # local-only placeholder values for compose and the apps
README.md                        # assessor path, how to run, data model and why, status table (draft exists; finished at the end)
Makefile                         # setup, dev, test, check-api, check-spec-first
scripts/
└── check-spec-first.sh          # verifies spec.md was committed before backend/ and frontend/ files

backend/
├── pyproject.toml / uv.lock
├── db-automation-apply/
│   ├── 001_schema.sql           # DDL: source of truth (already drafted)
│   └── README.md
├── alembic/                     # revision 0001 applies 001_schema.sql
├── openapi.json                 # generated from the app; the frontend's contract
├── scripts/export_openapi.py    # builds the app only, needs no database
├── src/app/
│   ├── main.py                  # create_app()
│   ├── core/                    # config, security (Basic auth), errors, logging
│   ├── db/                      # engine, session (pool settings)
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/routes/           # articles.py (writer router), public.py (public router)
│   └── domains/articles/
│       ├── models.py
│       ├── schemas.py           # request and response models, error envelope
│       ├── repository.py        # thin: locking and snapshot SQL only
│       └── service.py           # business rules, the transaction, the only committer
│   └── domains/ai/              # optional extra (A-7): draft generator, limits; no database access
└── tests/
    ├── conftest.py              # the _test database guard and the shared fixtures
    ├── unit/                    # rules that need no database (guard, validation)
    ├── integration/             # real _test PostgreSQL: lifecycle, concurrency, crash injection, triggers
    └── api/                     # auth matrix, status codes, route sweep, public schema

frontend/
├── package.json / pnpm-lock.yaml / eslint.config.mjs / vitest.config.ts
├── public/.gitkeep
├── src/
│   ├── proxy.ts                 # checks the Authorization header is present on /studio/**
│   ├── app/
│   │   ├── globals.css                   # Tailwind entry and the few design tokens
│   │   ├── (public)/docs/page.tsx            # public list (force-dynamic)
│   │   ├── (public)/docs/[slug]/page.tsx     # public article (force-dynamic, notFound())
│   │   ├── (studio)/studio/page.tsx          # article list and the "New article" button
│   │   ├── (studio)/studio/new/page.tsx      # write a new article directly (nothing exists until saved)
│   │   ├── (studio)/studio/[id]/page.tsx     # editor, preview, history
│   │   ├── (studio)/studio/actions.ts        # Server Actions (forward the header)
│   │   └── auth/challenge/route.ts           # returns 401 + WWW-Authenticate
│   ├── features/articles/       # editor, new-article form, history panel, conflict view
│   ├── components/ui/
│   └── lib/
│       ├── api/generated/       # generated types (never hand-edited)
│       ├── api/server-client.ts # per-call Authorization header
│       ├── markdown.ts          # one renderer + sanitizer, used by preview and public page
│       └── env.ts               # validated lazily
├── tests/                       # Vitest: markdown.ts, format.ts
└── e2e/                         # Playwright real-browser tests (make e2e)

Dockerfile / cloudbuild.yaml     # in backend/ and frontend/ (the Dockerfiles are built by Docker Compose; cloudbuild.yaml is low priority, drafted, not verified)
```

**Structure Decision**: Web application. `backend/` and `frontend/` sit side by side with `specs/`, `docs/` and the root `Makefile` in one repository. The only thing the two sides share is the generated OpenAPI contract. The specification stays at the repository root so the spec-first check has one clear target.

## Complexity Tracking

No Constitution Check violations, so nothing to justify.

Deliberate simplifications (not violations): the Repository layer is thin and holds only the locking and snapshot SQL; there is one `articles` domain; there is no background work, queue, cache or search.

## Amendments after implementation

Recorded in `spec.md` ("Amendments", A-1 to A-6) and built after the first plan was committed. The design decisions behind them:

- **A-1 Direct creation.** The slug cannot change after creation (FR-006), so it must be known at the first save. The new-article screen therefore fills the slug from the title, lets the writer edit it, and generates `article-<random>` when it is empty. The API is unchanged (`POST /articles` with title, slug, body and tags); nothing is stored until the writer saves.
- **A-2 Save & publish.** Done by the web app as two ordered calls (`PATCH`, then `POST …/publish` with the version the save returned), so no new API operation and no change to the atomic publish (INV-002). If the second call fails the screen says the draft was saved. A single combined endpoint was considered and rejected: it would add an operation and a second place for the check order (FR-033) to go wrong.
- **A-3 One width.** All layouts use the same container width; the article body keeps a shorter line length inside it.
- **A-4 OpenAPI tidy-up.** `app.openapi` is wrapped to replace FastAPI's default validation-error schema with the real error envelope, to drop an impossible 422, and to declare the Basic scheme on writer operations; the contract gained the 422 that path validation produces. Checked by `test_contract_matches_openapi.py`.
- **A-5 Test host guard.** `TEST_DATABASE_EXTRA_HOSTS` names a service host explicitly; the `_test` name rule is unchanged.
- **A-6 Sign-in challenge.** `proxy.ts` answers the challenge itself.

Constitution Check after the amendments: no violations. Principle II (specification before implementation) is satisfied by the original commit order; these amendments are recorded before the final commit, and the spec says plainly that they came later.

### A-7 AI draft generation (optional extra) and A-8 deferred preview

- **Shape.** Two writer operations: `GET /api/v1/ai/status` (is it on) and `POST /api/v1/ai/draft` (the writer's title, tags, optional notes and optional instructions in; a body, suggested tags and the unchanged title out). Neither touches the database. The AI code lives in its own package (`backend/src/app/domains/ai/`) so it can be deleted without touching the article code.
- **Model call.** The Anthropic Python SDK, asynchronously, using its streaming helper (`messages.stream`, reading `text_stream`): `model` from `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`), `max_tokens` capped by a setting, a system prompt that asks for the Markdown body only. The model writes plain Markdown (not JSON), so each piece can be shown at once; the writer's title and tags are never sent back or replaced. No prefill and no sampling parameters (both are refused by this model family). Thinking is not enabled: a first draft does not need it, and it keeps cost and delay low. Cost is about 2 to 3 cents per draft at the default size, and is capped by prepaid credit and the Console spend limit.
- **Streaming (A-9).** `POST /api/v1/ai/draft` answers with server-sent events (`text/event-stream`): `delta` events carry text, a final `done` event ends it, and an `error` event reports a failure after the stream has started. Everything that can fail before the first byte (sign-in, validation, off, rate limit, and the model's first reply) is answered with a normal status code and the usual error envelope: the route waits for the first piece before it returns. The web app reaches it through one route handler (`/studio/ai-draft`) that passes the stream through with the browser's own `Authorization` header, so the key and the API address stay on the servers. The browser reads the stream and fills the body as it arrives; a Stop button aborts it. The response is marked `no-store` and `no-transform` so nothing buffers it.
- **Guards.** Off by default (`AI_ENABLED`); on without a key is a start-up error; title up to 200 characters, up to 10 tags, notes up to 5,000 and instructions up to 1,000, and a token cap on the output; an in-memory per-instance request limit (default 5 a minute) answered with 429; upstream failures, refusals and unusable replies become a generic 502 with no internal detail; neither the key nor the text is logged.
- **Testing.** The model client is injected through `app.state`, so every test uses a fake that records the request; no test reaches the network. A live check needs a key and is a manual step (quickstart scenario 12).
- **Screens.** One "Generate with AI" button in a bar just above the body field, on the new-article screen and in the editor. It is **always shown**: enabled when the status says on, otherwise disabled with a note on how to switch it on (so it is discoverable). It sends the current title, tags and body (as notes); the proposal replaces the body as it streams in (after a confirmation if there is text); the title and tags are never changed; it is labelled as AI output to review, and a Stop button keeps what has arrived.
- **A-8.** The preview renders `useDeferredValue(body)`, so typing is never blocked by a long Markdown render.
- **Constitution Check.** Principle V (as amended 1.0.1) allows this: it was built after the core was complete, is off by default, writes nothing itself, has limits, and its tests never call the API.
