# Docs Studio

A small content management service for internal writers (an API plus a minimal UI) and a public documentation site where only published articles can be read. Built with FastAPI, PostgreSQL, Next.js and Tailwind CSS.

## For assessors: start here

There are two ways to check the work. Use whichever you prefer:

1. **On your own machine with Docker** (nothing else to install): see "Running it locally" below.
2. **On the deployed site** (Cloud Run), because assessors cannot reach the authors' database:

- **URL**: https://docs-studio-web-cacovrwumq-an.a.run.app (public pages at `/docs`, writer area at `/studio`). The API is at https://docs-studio-api-cacovrwumq-an.a.run.app. The database is a small Cloud SQL instance that may be stopped or deleted after the assessment, so the site can go away.
- **Writer area** (`/studio`) on the deployed site asks for a username and password (HTTP Basic authentication). The credentials are **shared outside this repository**. The public pages (`/docs`) need no sign-in. A local Docker run has **no login by default** (see below).
- **What was checked on the deployed site**: the public list and the "not found" answers, that the writer area asks for credentials and the API refuses wrong ones, the production security headers, and that the API reaches its database. The writer scenarios of `specs/001-docs-studio/quickstart.md` (create, publish, restore and so on) were **not** run by the author on the deployed site, because the credentials are kept private; the same scenarios were run on the local Docker system.
- The Cloud Run file (`cloudbuild.yaml`) is optional and is **not part of the assessed scope**; it was built and deployed once by hand (2026-11-01) with the files in this repository. The Dockerfiles are also used by the local Docker run.

Things worth trying: publish an article, edit the draft and check the public page still shows the published text, take it down and check the public page returns "not found", restore an old version, try to delete the live version, and save from two browser tabs to see the conflict message.

## What it does

The idea that shapes the design: **a writer can edit freely without ever changing what readers see, and what readers see is always a frozen snapshot of what was last published.** A draft and published content never share a row; every publish creates an immutable, numbered snapshot inside one atomic transaction.

> **Status: the backend, the web app and the local Docker run are built and tested; the Cloud Run deployment is not.** 362 backend tests (on a real PostgreSQL) and 25 frontend tests pass with `make test`, and the same backend suite passes inside Docker with `docker compose --profile test run --rm test`. The web screens were built and checked over HTTP and by screenshots of the running app, but the interactive flows (saving, publishing, the conflict screen, the sign-in prompt) were **not driven end to end by the author in a browser**, and the deployed site does not exist yet. The table at the end gives the status of every feature.

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

This was run from a clean copy of the repository (no installed dependencies, no `.env`) and the whole system came up in well under a minute with warm caches. The results of the ten quickstart scenarios are in `specs/001-docs-studio/quickstart-results.md`.

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

## Design trade-offs made under the time limit

The time limit shaped four decisions. In short: reads are kept simple and always correct instead of fast, authentication is kept to the smallest thing that protects the writer API, tests run on a real database at the cost of needing a reachable PostgreSQL, and deployment work is kept out of the assessed scope. In more detail:

- **Correctness over speed of reads.** Public pages are rendered dynamically on every request and nothing is cached. That costs some read performance, but an unpublished article disappears on the next request, which the assignment's "404 for taken-down articles" requires, and a caching layer is out of scope anyway.
- **Authentication added, but kept minimal.** The assignment treats authentication as out of scope, but the service is exposed on the internet, so the writer area uses one shared username and password (HTTP Basic). It is checked in the API itself, so calling the API directly is protected too. It is one explicit switch (`BASIC_AUTH_ENABLED`): required in production, and off by default for a local run so the project behaves as the assignment describes (no authentication). There are no accounts, roles or logout.
- **A real database in tests, and Docker for the local run.** Tests run on a real `_test` database (never mocks) because the guarantees live in the database, and `docker compose up --build` gives anyone a working system from a fresh checkout with only Docker installed. The trade-off is that running locally needs Docker (or a PostgreSQL you install yourself), and the tests need that database to be reachable; the deployed site needs nothing installed.
- **Cloud Run deployment is low priority and outside the assessed scope.** It was done last, by hand, on a small instance; there is no automatic deployment from GitHub yet.

## Optional extras (outside the assessed scope)

- **AI body generation** (off by default). In the editor, the "Generate with AI" button (always visible; disabled with a note when the feature is off) asks Claude (`claude-sonnet-4-6`, changeable with `ANTHROPIC_MODEL`) to write the body from the title, tags and any notes already entered. It returns a **proposal only**: the text appears in the body field progressively as it is written (a Stop button keeps what has arrived), and nothing is saved or published until the writer saves. To try it, set `AI_ENABLED=true` and your own `ANTHROPIC_API_KEY` in `.env` (never commit the key). Guards: off unless switched on (and the service refuses to start if it is on without a key), input length limits, a token cap, five requests a minute per instance, a generic error message that gives no internal detail, and no logging of the key or the text. On a local run the key lives in `.env` (which Git ignores); on Google Cloud it is kept in Secret Manager (`anthropic-api-key`) and handed to the service by `backend/cloudbuild.yaml` only when `_AI_ENABLED=true` (used by the deployed API only if AI is switched on; AI is off on the deployed site). Cost is about 2 to 3 cents a draft and is capped by the prepaid credit on your account. The tests use a fake model and never call the API; the real model has not been called (see `specs/001-docs-studio/quickstart-results.md`, scenario 12).

## Images

The photo in the web app (the public list banner) is from Unsplash, which licenses it for free use. It was downloaded once and is kept in `frontend/public/images/`, so the app never loads an image from another site (the Content Security Policy only allows `'self'` images, and a test checks that no source file names an image host).

## Improvements with more time

- Per-person accounts with a proper sign-in and sign-out instead of one shared Basic credential.
- Save as Version and a Diff View between two versions.
- Rate limiting on the sign-in challenge, and an audit log of who published or deleted what.
- Real pagination (cursor-based) and a search over published articles.
- A cache for public pages with explicit invalidation on publish and unpublish, once the 404 requirement can be proven to hold with it.
- Try the AI draft helper against the real model and tune its prompt (it was checked only with a local stand-in; see "Optional extras" below).
- CI that runs the tests and the spec-first check, and infrastructure as code for Cloud Run and Cloud SQL.

## Features and their status

Status values: **Done**, **Partial**, **Not done**. *Done* means built and covered by automated tests; for features with a screen, "screen not driven in a browser" means the API behaviour is tested and the page was built and fetched over HTTP, but nobody clicked through it in a real browser. For anything not done, the last column says how it would be built. The task numbers are in `specs/001-docs-studio/tasks.md`.

| Feature | Status | If not done: how it would be built |
|---|---|---|
| Create and edit drafts, list, Markdown preview | Done (screen not driven in a browser) | n/a |
| Publish (atomic, immutable snapshot, first `published_at`) | Done | n/a |
| Unpublish (keeps snapshots and `published_at`) | Done | n/a |
| Version history, Restore, Delete (live version protected) | Done (screen not driven in a browser) | n/a |
| Conflict detection (`expected_draft_version`, 409) | Done (the conflict screen was not driven in a browser) | n/a |
| Public list and article (live snapshot only; same 404) | Done | n/a |
| Writer area protected by Basic authentication (required in production, off by default locally) | Done (the browser sign-in prompt was not observed) | n/a |
| Optional: Idempotent Publish | Done | n/a |
| Optional: Slug collision handling | Done | n/a |
| Extra (outside the assessed scope): AI body generation with Claude | Done, tested with a fake model; not run against the real model | The real call needs a key and a few cents of credit; run quickstart scenario 12 |
| Automated tests for every invariant (INV-1 to INV-6) | Done | n/a |
| Local run with Docker Compose (`docker compose up --build`) | Done | n/a |
| Cloud Run deployment | Partial: deployed and its public side checked; the writer scenarios were not run on it | Build with `cloudbuild.yaml`; create Cloud SQL, Artifact Registry, Secret Manager and the service accounts by hand (Phase 12, low priority) |
| AI draft generation | Not done: excluded from the plan | See "Improvements with more time" above |

## Repository layout

```text
backend/     FastAPI API; the DDL is in db-automation-apply/
frontend/    Next.js web app (public site and the writer area)
specs/       Spec Kit artifacts for this feature
docs/        Requirements and architecture (English); docs/ja/ has the Japanese versions
scripts/     check-spec-first.sh
```
