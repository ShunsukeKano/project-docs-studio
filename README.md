# Docs Studio

A small content management service for internal writers (an API plus a minimal UI) and a public documentation site where only published articles can be read. Built with FastAPI, PostgreSQL, Next.js and Tailwind CSS.

**The idea that shapes the design:** a writer can edit freely without ever changing what readers see, and what readers see is always a frozen snapshot of what was last published. A draft and published content never share a row; every publish creates an immutable, numbered snapshot inside one atomic transaction.

## For assessors: start here

There are two ways to check the work. Please use whichever you prefer.

| | On your own machine | On the deployed site (Cloud Run) |
|---|---|---|
| What you need | Docker only | A browser |
| How | `cp .env.example .env`, then `docker compose up --build`, then open `http://localhost:3000` | The address, and the writer username and password, are **sent to assessors together, outside this repository** (nothing is written here) |
| Public pages | `/docs` | `/docs` (no sign-in) |
| Writer area | `/studio`, **no login by default** | `/studio`, asks for the username and password (HTTP Basic authentication) |
| Notes | Details in "Running it locally" below | The database is a small Cloud SQL instance that may be stopped or deleted after the assessment, so the site can go away. Assessors cannot reach the authors' database, which is why the deployed site exists |

**How to confirm** (about five minutes): publish an article; edit the draft and check the public page still shows the published text; take it down and check the public page returns "not found"; restore an old version; try to delete the live version; save from two browser tabs to see the conflict message.

The Cloud Run files (`cloudbuild.yaml`) are optional. The Dockerfiles are also used by the local Docker run.

## Status at a glance

| Area | Status | Evidence |
|---|---|---|
| Backend, web app, local Docker run, Cloud Run deployment | Built and working | See "What was checked, and how" |
| Backend tests | 367, on a real PostgreSQL | `make test`; the same suite passes in Docker with `docker compose --profile test run --rm test` |
| Frontend tests | 29 (Vitest) | `make test` |
| Browser tests | 21 (Playwright), against a throwaway Docker system | `make e2e`; separate from `make test` |
| Continuous integration | GitHub Actions, on every push to `main` and every pull request | `.github/workflows/ci.yml`: backend checks on a PostgreSQL 17 service, frontend and API-contract checks, and the spec-first check. It does **not** run the browser tests and does **not** gate the Cloud Build deploy |
| Every feature | See the table at the end | "Features and their status" |

The 21 browser tests cover: create, save and publish in one step, history, Restore, delete, Unpublish, the edit-conflict screen with "Resubmit", and (with a stand-in for the model) the streamed AI draft.

## What was checked, and how

| What was checked | How | Notes |
|---|---|---|
| 367 backend and 29 frontend tests | Automated | `make test`; also run by GitHub Actions |
| The ten quickstart scenarios, on the local Docker system | Scripts | Results in `specs/001-docs-studio/quickstart-results.md` |
| The writer screens, end to end in a real browser (headless Chrome) | Automated | Kept as the 21 Playwright tests (`make e2e`) |
| The deployed site from outside: the public list and the "not found" answers, that the writer area asks for credentials and the API refuses wrong ones, the production security headers, and that the API reaches its database | By hand, not signed in | |
| The deployed AI settings (the key comes from Secret Manager and the service starts), and the AI stream with a stand-in for the model | By hand and by script | `specs/001-docs-studio/quickstart-results.md`, scenario 12 |
| That the deployed site runs | By hand, signed in | |
| The writer scenarios of `specs/001-docs-studio/quickstart.md` on the deployed site | By hand, signed in | **No detailed record** (no timings or transcripts) |
| The AI button against the real Claude model on the deployed site | By hand, signed in | **No detailed record** |
| The browser's own sign-in box | By hand | **No detailed record** |
| The goal "first article published in under three minutes" | By hand | **No detailed record** |

## How the work was specified (spec first)

The specification came before any implementation, using Spec Kit:

| Artifact | Where |
|---|---|
| Constitution (the project's rules) | `.specify/memory/constitution.md` |
| Specification | `specs/001-docs-studio/spec.md` |
| Plan, research and data model | `specs/001-docs-studio/plan.md`, `research.md`, `data-model.md` |
| API contract | `specs/001-docs-studio/contracts/openapi.yaml` |
| Tasks, in build order | `specs/001-docs-studio/tasks.md` |
| Requirements and architecture (English; Japanese in `docs/ja/`) | `docs/requirements.md`, `docs/nextjs-fastapi-architecture.html` |

`scripts/check-spec-first.sh` (run it with `make check-spec-first`) verifies that `spec.md` was committed before any file under `backend/` or `frontend/`. History has not been rewritten.

## Running it locally

**With Docker (the short way; only Docker is needed):**

```bash
cp .env.example .env        # the writer login is off by default for a local run
docker compose up --build   # starts PostgreSQL, applies the schema, then the API (port 8000) and the web app (port 3000)
```

This was run from a clean copy of the repository (no installed dependencies, no `.env`) and the whole system came up in well under a minute with warm caches.

The development database lives in a Docker volume, so its data survives `docker compose down`; only `docker compose down -v` removes it. The test database is in memory and is reset by every run.

Open `http://localhost:3000`: the public pages are at `/docs`, and the writer area is at `/studio` (no login by default; set `BASIC_AUTH_ENABLED=true` with `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` to turn it on).

**Without containers for the app** (Python 3.12 with uv, Node.js 22 with pnpm, and a PostgreSQL database; the Compose `db` and `db-test` services are the easiest source):

```bash
make setup   # install dependencies, start the Compose databases, apply the schema
make dev     # start the API and the web app
make test    # run every test (needs TEST_DATABASE_URL; the database name must end in _test)
```

**Run the tests with only Docker installed:**

```bash
make test-docker   # docker compose --profile test run --rm test
```

**Drive the screens in a real browser (optional, needs Docker and Google Chrome):**

```bash
make e2e   # 21 Playwright tests against a throwaway Docker system
```

`make e2e` builds and starts a separate system from `compose.e2e.yaml` (its own database, kept in memory, on ports 18000 and 13000; the writer login and the AI feature are off), runs the browser tests in `frontend/e2e/`, and always removes the system afterwards, so your development data is not touched. It is not part of `make test`. The AI button is only checked for its state; the tests never call the model.

Configuration is by environment variables (`.env.example` lists them): `DATABASE_URL`, `TEST_DATABASE_URL`, `BASIC_AUTH_ENABLED`, `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD`, `API_BASE_URL`. `DATABASE_URL` can point at any PostgreSQL, for example Cloud SQL through the Cloud SQL Auth Proxy. Tests refuse to run unless the database name ends in `_test` and the host is local (the Compose test container names its `db-test` host explicitly).

## Data model

Two tables (the DDL is `backend/db-automation-apply/001_schema.sql`; the explanation is `specs/001-docs-studio/data-model.md`):

- **`articles`**: one row per article, holding its **draft** (`draft_title`, `draft_body`, `draft_tags`), the optimistic-concurrency token `draft_version`, the numbering counter `last_version_number`, the `status` (`draft`, `published`, `unpublished`), the pointer `current_published_version_id`, and `published_at` (the first publication time).
- **`article_versions`**: one row per published **snapshot** (`version_number`, `title`, `body`, `tags`). A snapshot is never changed, and the one the pointer references (the *protected* version) is never deleted.

### Why this model

- Separating the draft from the snapshots makes the two assessed promises easy to keep: editing never touches what readers see, and a published snapshot can never change.
- The pointer is a single column, so publishing is "insert one row, move one pointer, set the status" in one transaction, and a reader's page is one join.
- The database enforces what the application enforces: a trigger rejects any change to a snapshot, a CHECK constraint stops "published without a pointer", a composite foreign key stops deleting the live snapshot and pointing at another article's version, and a guard trigger stops a published article going back to draft. A bug cannot store a bad state.
- A per-article counter (`last_version_number`) numbers snapshots, so a number is never reused even after a deletion.
- It follows the recommended model in the assignment, with two additions: `last_version_number`, and the constraints above.

## Optional extras

**AI body generation** (off by default; **switched on for the deployed site**). In the editor, the "Generate with AI" button (always visible; disabled with a note when the feature is off) asks Claude (`claude-sonnet-4-6`, changeable with `ANTHROPIC_MODEL`) to write the body from the title, tags and any notes already entered.

| | |
|---|---|
| What it returns | A **proposal only**. The text appears in the body field progressively as it is written (a Stop button keeps what has arrived), and nothing is saved or published until the writer saves |
| To try it locally | Set `AI_ENABLED=true` and your own `ANTHROPIC_API_KEY` in `.env` (never commit the key) |
| Guards | Off unless switched on (the service refuses to start if it is on without a key), input length limits, a token cap, five requests a minute per instance, a generic error message that gives no internal detail, and no logging of the key or the text |
| Where the key lives | On a local run, in `.env` (which Git ignores). On Google Cloud, in Secret Manager (`anthropic-api-key`), handed to the API service as `ANTHROPIC_API_KEY`, with `AI_ENABLED=true` set on the service. No key is in the code, the image or any file in this repository. The service settings are kept across the automatic deploys, and `backend/cloudbuild.yaml` maps the secret only when built with `_AI_ENABLED=true` |
| Who can use it | On the deployed site, only a signed-in writer, so the cost is limited to people who have the writer credentials |
| Cost | About 2 to 3 cents a draft, capped by the prepaid credit on your account |
| Tests | A fake model; the tests never call the API |

## Features and their status

Status values: **Done**, **Partial**, **Not done**. *Done* means built and covered by automated tests; for features with a screen, the screen was also driven in a real browser (see "What was checked, and how"). For anything not done, the last column says how it would be built. The task numbers are in `specs/001-docs-studio/tasks.md`.

| Feature | Status | If not done: how it would be built |
|---|---|---|
| Create and edit drafts, list, Markdown preview | Done | n/a |
| Publish (atomic, immutable snapshot, first `published_at`) | Done | n/a |
| Unpublish (keeps snapshots and `published_at`) | Done | n/a |
| Version history, Restore, Delete (live version protected) | Done | n/a |
| Conflict detection (`expected_draft_version`, 409) | Done | n/a |
| Public list and article (live snapshot only; same 404) | Done | n/a |
| Writer area protected by Basic authentication (required in production, off by default locally) | Done | n/a |
| Optional: Idempotent Publish | Done | n/a |
| Optional: Slug collision handling | Done | n/a |
| Extra: AI body generation with Claude | Done and switched on for the deployed site; tested with a fake model | n/a |
| Automated tests for every invariant (INV-1 to INV-6) | Done | n/a |
| Continuous integration (GitHub Actions) | Done; does not run the browser tests and does not gate the deploy | n/a |
| Local run with Docker Compose (`docker compose up --build`) | Done | n/a |
| Cloud Run deployment (with automatic deploys from GitHub) | Done | n/a. It was built with `cloudbuild.yaml`, and Cloud SQL, Artifact Registry, Secret Manager and the service accounts were created by hand (low priority) |

## Repository layout

```text
backend/     FastAPI API; the DDL is in db-automation-apply/
frontend/    Next.js web app (public site and the writer area)
specs/       Spec Kit artifacts for this feature
docs/        Requirements and architecture (English); docs/ja/ has the Japanese versions
scripts/     check-spec-first.sh
```
