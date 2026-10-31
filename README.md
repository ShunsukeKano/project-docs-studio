# Docs Studio

A small content management service for internal writers (an API plus a minimal UI) and a public documentation site where only published articles can be read. Built with FastAPI, PostgreSQL, Next.js and Tailwind CSS.

## For assessors: start here

There are two ways to check the work. Use whichever you prefer:

1. **On your own machine with Docker** (nothing else to install): see "Running it locally" below.
2. **On the deployed site** (Cloud Run), because assessors cannot reach the authors' database:

- **URL**: *(to be added when it is deployed)*
- **Writer area** (`/studio`) on the deployed site asks for a username and password (HTTP Basic authentication). The credentials are **shared outside this repository**. The public pages (`/docs`) need no sign-in. A local Docker run has **no login by default** (see below).
- The site and its database are kept running while the work is assessed.
- The Cloud Run file (`cloudbuild.yaml`) is optional and is **not part of the assessed scope**; it is drafted and was not verified until the URL above is filled in. The Dockerfiles are used by the local Docker run.

Things worth trying: publish an article, edit the draft and check the public page still shows the published text, take it down and check the public page returns "not found", restore an old version, try to delete the live version, and save from two browser tabs to see the conflict message.

## What it does

The idea that shapes the design: **a writer can edit freely without ever changing what readers see, and what readers see is always a frozen snapshot of what was last published.** A draft and published content never share a row; every publish creates an immutable, numbered snapshot inside one atomic transaction.

> **Status: planning is complete, implementation has not started.** This README is a draft written before the code. Anything about running the project is marked *(planned)* until it has been built and run, and the status table at the end is updated when the work is done.

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

`scripts/check-spec-first.sh` *(planned)* verifies that `spec.md` was committed before any file under `backend/` or `frontend/`. History has not been rewritten.

## Running it locally *(planned; not yet built)*

**With Docker (the short way; only Docker is needed):**

```bash
cp .env.example .env        # the writer login is off by default for a local run
docker compose up --build   # starts PostgreSQL, applies the schema, then the API (port 8000) and the web app (port 3000)
```

Open `http://localhost:3000`: the public pages are at `/docs`, and the writer area is at `/studio` (no login by default; set `BASIC_AUTH_ENABLED=true` with `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` to turn it on).

**Without containers for the app** (Python 3.12 with uv, Node.js 22 with pnpm, and a PostgreSQL database; the Compose `db` and `db-test` services are the easiest source):

```bash
make setup   # install dependencies, start the Compose databases, apply the schema, generate the API types
make dev     # start the API and the web app
make test    # run every test (needs TEST_DATABASE_URL; the database name must end in _test)
```

**Run the tests with only Docker installed:**

```bash
make test-docker   # docker compose --profile test run --rm test
```

Configuration is by environment variables (`.env.example` lists them): `DATABASE_URL`, `TEST_DATABASE_URL`, `BASIC_AUTH_ENABLED`, `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD`, `API_BASE_URL`. `DATABASE_URL` can point at any PostgreSQL, for example Cloud SQL through the Cloud SQL Auth Proxy. Tests refuse to run unless the database name ends in `_test` and the host is local.

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
- **Cloud Run deployment is low priority.** `cloudbuild.yaml` is drafted but was not part of the assessed scope and must not be treated as verified until it has been run. (The Dockerfiles are built by the Docker Compose run.)

## Improvements with more time

- Per-person accounts with a proper sign-in and sign-out instead of one shared Basic credential.
- Save as Version and a Diff View between two versions.
- Rate limiting on the sign-in challenge, and an audit log of who published or deleted what.
- Real pagination (cursor-based) and a search over published articles.
- A cache for public pages with explicit invalidation on publish and unpublish, once the 404 requirement can be proven to hold with it.
- An optional AI draft helper (it would use the Claude API on prepaid credit, return a proposal only and never save or publish anything by itself).
- CI that runs the tests and the spec-first check, and infrastructure as code for Cloud Run and Cloud SQL.

## Features and their status

Status values: **Done**, **Partial**, **Not done**. Nothing is built yet, so every feature below is *Not done*; this table is updated when the work is finished. For anything not done, the last column says how it will be (or would have been) built. The task numbers are in `specs/001-docs-studio/tasks.md`.

| Feature | Status | If not done: how it would be built |
|---|---|---|
| Create and edit drafts, list, Markdown preview | Not done | Backend: models, schemas, service and routes with the tests first (tasks Phase 3). Frontend: the editor form with a live preview using one shared sanitizer (Phase 11) |
| Publish (atomic, immutable snapshot, first `published_at`) | Not done | One transaction under the article's row lock: version check, next number from a per-article counter, insert the snapshot, move the pointer (Phase 4) |
| Unpublish (keeps snapshots and `published_at`) | Not done | A status-only change under the same row lock (Phase 6) |
| Version history, Restore, Delete (live version protected) | Not done | History query; Restore as one `UPDATE` of the draft columns; Delete takes the same row lock and refuses the pointed-at version, with the foreign key as the backstop (Phase 7) |
| Conflict detection (`expected_draft_version`, 409) | Not done | A conditional `UPDATE ... WHERE draft_version = :expected` on edit and Restore, and the same check under the lock on Publish (Phase 8) |
| Public list and article (live snapshot only; same 404) | Not done | One join from the article to its live snapshot; the same 404 for every kind of miss; no caching (Phase 5) |
| Writer area protected by Basic authentication (required in production, off by default locally) | Not done | A router-level dependency in FastAPI, switched by `BASIC_AUTH_ENABLED`, forwarded by Next.js Server Actions, with a 401 challenge route (Phases 2, 10 and 11) |
| Optional: Idempotent Publish | Not done | Compare the draft with the live snapshot under the lock; create nothing if equal (Phase 9) |
| Optional: Slug collision handling | Not done | Append the smallest free number and retry on a unique violation (Phase 3) |
| Automated tests for every invariant (INV-1 to INV-6) | Not done | Written first in each phase, on a real `_test` database, run by `make test` (all phases) |
| Local run with Docker Compose (`docker compose up --build`) | Not done | `compose.yaml` with `db`, `db-test`, `migrate`, `backend` and `frontend` built from the Dockerfiles (Phases 1 and 12) |
| Cloud Run deployment | Partial: files drafted, not verified | Build with `cloudbuild.yaml`; create Cloud SQL, Artifact Registry, Secret Manager and the service accounts by hand (Phase 12, low priority) |
| AI draft generation | Not done: excluded from the plan | See "Improvements with more time" above |

## Repository layout

```text
backend/     FastAPI API; the DDL is in db-automation-apply/
frontend/    Next.js web app (public site and the writer area)
specs/       Spec Kit artifacts for this feature
docs/        Requirements and architecture (English); docs/ja/ has the Japanese versions
scripts/     check-spec-first.sh (planned)
```
