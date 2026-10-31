# Implementation Plan: Docs Studio

**Branch**: none (no git branch is created; the work lives in `specs/001-docs-studio`) | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-docs-studio/spec.md`

## Summary

Docs Studio lets a small internal team write, publish, unpublish and version articles, and lets anyone read published articles. The primary requirement is **data integrity**: a draft and published content never share a row, every publish creates an immutable numbered snapshot inside one atomic transaction, the protected (live) snapshot can never be deleted, Restore only copies into the draft, and concurrent edits are detected with an `expected_draft_version` check.

Technical approach (decided in [research.md](./research.md)): a FastAPI backend on PostgreSQL where every writer operation takes the article's row lock first and decides against the locked row; a Next.js (App Router) frontend that renders public pages dynamically and forwards the writer's Basic credentials to the API; the schema kept as numbered SQL files in `backend/db-automation-apply/` and applied by Alembic; and automated tests, run on a real PostgreSQL `_test` database, that cover every invariant. The database enforces what the application also enforces (triggers, CHECK and composite foreign key), so a bug cannot store a bad state.

Out of this plan, on purpose: AI draft generation (if it is ever built it uses the Claude API on prepaid credit), Save as Version, Diff View and any caching layer.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 in strict mode on Node.js 22 (frontend)

**Primary Dependencies**: Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), asyncpg, Alembic, uvicorn. Frontend: Next.js 16 (App Router), React 19, `openapi-typescript` and `openapi-fetch` (types and client generated from the contract), Tailwind CSS (utility-first styling, the current major version, confirmed at setup), Zod (form checks), a Markdown renderer with a sanitizer (`react-markdown` with `rehype-sanitize`). Tooling: uv (Python), pnpm (Node), ruff and mypy, ESLint.

**Storage**: PostgreSQL. Production on Cloud SQL. Local runs use PostgreSQL 17 started by Docker Compose (`db` for development, `db-test` for tests), or Cloud SQL through the Auth Proxy; the target is chosen by `DATABASE_URL` and `TEST_DATABASE_URL`, and development, test and production databases are separate. The DDL is the numbered SQL in `backend/db-automation-apply/` (source of truth).

**Testing**: pytest with pytest-asyncio and httpx (`ASGITransport`) against a real PostgreSQL `_test` database (no database mocks); Vitest for the shared Markdown sanitizer; `tsc --noEmit` and ESLint for the frontend. One command, `make test`, runs everything including the OpenAPI drift check.

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
| V. Simplicity and Scope | Core first; only Idempotent Publish and Slug collision handling; AI, Save as Version, Diff View excluded; deployment low priority | PASS: scope list above | PASS: no excluded feature appears in the contract or the model |
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
README.md                        # assessor path, how to run, data model and why, trade-offs, status table (draft exists; finished at the end)
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
│   │   ├── (studio)/studio/page.tsx          # article list
│   │   ├── (studio)/studio/[id]/page.tsx     # editor, preview, history
│   │   ├── (studio)/studio/actions.ts        # Server Actions (forward the header)
│   │   └── auth/challenge/route.ts           # returns 401 + WWW-Authenticate
│   ├── features/articles/       # editor form, history panel, conflict view
│   ├── components/ui/
│   └── lib/
│       ├── api/generated/       # generated types (never hand-edited)
│       ├── api/server-client.ts # per-call Authorization header
│       ├── markdown.ts          # one renderer + sanitizer, used by preview and public page
│       └── env.ts               # validated lazily
└── tests/                       # Vitest for markdown.ts

Dockerfile / cloudbuild.yaml     # in backend/ and frontend/ (the Dockerfiles are built by Docker Compose; cloudbuild.yaml is low priority, drafted, not verified)
```

**Structure Decision**: Web application. `backend/` and `frontend/` sit side by side with `specs/`, `docs/` and the root `Makefile` in one repository. The only thing the two sides share is the generated OpenAPI contract. The specification stays at the repository root so the spec-first check has one clear target.

## Complexity Tracking

No Constitution Check violations, so nothing to justify.

Deliberate simplifications (not violations): the Repository layer is thin and holds only the locking and snapshot SQL; there is one `articles` domain; there is no background work, queue, cache or search.
