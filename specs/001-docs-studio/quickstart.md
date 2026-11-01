# Quickstart: validating Docs Studio end to end

Phase 1 output of `/speckit-plan`. This is a run-and-validate guide, not an implementation guide. It says **what to run and what you should see**; the contract is in [contracts/openapi.yaml](./contracts/openapi.yaml), the data rules in [data-model.md](./data-model.md), and the work breakdown in `tasks.md`. Commands marked *(after implementation)* do not exist yet.

## Prerequisites

Pick one way to run it:

- **With Docker (recommended; nothing else to install)**: Docker with Compose.
- **Natively**: Python 3.12 with uv, Node.js 22 with pnpm, and PostgreSQL. The easiest PostgreSQL is the Compose `db` and `db-test` services (`docker compose up -d db db-test`); Cloud SQL through the Cloud SQL Auth Proxy also works.
- **Or use the deployed site** (the URL is in `README.md`; the Basic credentials are shared outside the repository) and skip to the scenarios.

Environment variables (copy `.env.example` to `.env`; it turns the writer login **off** for a local run, so no credentials are needed; set `BASIC_AUTH_ENABLED=true` and the two credentials to try the login): `DATABASE_URL` (development), `TEST_DATABASE_URL` (the name must end in `_test` and the host must be local), `BASIC_AUTH_ENABLED`, `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD`, `API_BASE_URL` (the frontend's address for the API). Development, test and production databases are separate.

## Setup and run *(after implementation)*

```bash
cp .env.example .env              # no sign-in by default for a local run
docker compose up --build         # database, schema, API (port 8000) and web app (port 3000)
```

Or natively:

```bash
make setup           # install dependencies; start the Compose databases; apply the schema; generate API types
make dev             # start the API and the web app
make test            # backend tests (real _test database), OpenAPI drift check, frontend checks
make check-api       # regenerate openapi.json and the frontend types; fails on any difference
make check-spec-first   # verify spec.md was committed before any backend/ or frontend/ file
```

Expected: the web app answers on `http://localhost:3000` (public pages at `/docs`, the writer area at `/studio`), `make test` passes with every invariant covered, and `make check-spec-first` prints success. `make test` refuses to start if `TEST_DATABASE_URL` does not name a local database ending in `_test`.

## Validation scenarios

Each scenario maps to a user story in [spec.md](./spec.md). Use the browser, or `curl` against the API with `-u "$BASIC_AUTH_USER:$BASIC_AUTH_PASSWORD"` for writer routes. `$API` is the API base (for example `http://localhost:8000/api/v1`).

### 1. Create and edit a draft (User Story 1)

1. Create an article (`POST $API/articles` with a title, a slug, a body and tags).
2. Edit it (`PATCH $API/articles/{id}` with `expected_draft_version`).

**Expect**: 201 then 200; `draft_version` goes 1 → 2; the status is `draft`; the public list (`GET $API/public/articles`, no credentials) does not show it. Creating again with the same slug returns a slug with `-2`, and a PATCH that includes `slug` returns 422.

### 2. Publish, and what readers see (User Stories 2 and 3)

1. Publish (`POST …/publish` with the current `draft_version`).
2. Edit the draft again without publishing.
3. Open the public article (`GET $API/public/articles/{slug}`).

**Expect**: 201 with `created: true` and version 1; `published_at` is set. The public article shows the **published** text, not the new draft. The public list shows title, tags and `published_at`, with `updated_at` null until a republish.

### 3. Republish keeps the first date (User Story 2)

Publish again after editing.

**Expect**: 201, version 2 is now live, `published_at` is unchanged, and the public list now shows an `updated_at`.

### 4. Unpublish keeps history (User Story 4)

1. Unpublish.
2. Fetch the public article, a never-published article's slug, and a made-up slug.
3. Open the version history as a writer.

**Expect**: the three public requests return the **same 404 with the same body**; the writer still sees every snapshot, and `published_at` is unchanged. Unpublishing again returns 409 `not_published`.

### 5. Restore never harms history (User Story 5)

Restore version 1 into the draft (`POST …/versions/1/restore` with the current `draft_version`).

**Expect**: 200; only the draft changed and `draft_version` went up by one; the list of snapshots, the status, the live pointer and `published_at` are identical before and after; nothing was published.

### 6. The protected version cannot be deleted (User Story 5)

1. Delete the live version (`DELETE …/versions/{n}`), then unpublish and try again.
2. Delete an older version.

**Expect**: 409 `version_is_live` both times (also after unpublishing) and the snapshot still exists; the older version returns 204 and its number is never reused. A missing number returns 404.

### 7. Conflicting edits (User Story 6)

Open the same draft in two browser tabs. Save in the first, then in the second.

**Expect**: the second save is refused with 409 `version_conflict` carrying the current `draft_version`; nothing is overwritten; the second tab keeps what its writer typed and offers "reload latest" or "resubmit". A publish with an old `expected_draft_version` also returns 409 and creates no snapshot.

### 8. Idempotent Publish (User Story 7)

Publish, then publish again with no changes; then unpublish and publish with no changes.

**Expect**: 200 with `created: false` and still one snapshot both times; after the unpublish, the article is live again with its original `published_at`.

### 9. Writer area is protected (User Story 8)

Turn the login on first: set `BASIC_AUTH_ENABLED=true` and the two credentials (a local run has it off by default).

Call a writer route with no credentials, wrong credentials and right credentials; call a public route with and without credentials.

**Expect**: 401 with `WWW-Authenticate: Basic` for the first two (even for an article that does not exist, because authentication comes first); success with the right ones; public routes work either way. In the browser, `/studio` prompts for credentials.

### 10. No caching (User Story 3)

Reload a public article, unpublish it, and reload again.

**Expect**: the article is gone on the very next request.

### 11. Write a new article directly and publish it in one step (User Stories 1 and 2, amendments A-1 and A-2)

In the browser, open `/studio`, press "New article", type a title, some tags and a body, and press "Save & publish". Then change the title in the editor and press "Save & publish" again.

**Expect**: the screen is the full editor with a live preview and **no article exists yet** (the list is unchanged until you save); the slug fills in from the title (and a pasted address is reduced to the slug); after "Save & publish" the editor opens for the new article with the status Published; with an unsaved change the button reads "Save & publish", and pressing it saves and publishes the new text as version 2 with the message "Saved and published as version 2". If publishing is refused after the save, the message says the changes were saved.

### 12. Generate the body with AI (User Story 9, optional extra; needs an API key)

Off by default. In the editor or on the new-article screen the "Generate with AI" button is always visible; with the feature off it is disabled and says how to switch it on. To try it, put `AI_ENABLED=true` and your own `ANTHROPIC_API_KEY` in `.env` (never commit it) and restart. Enter a title (and perhaps tags) and press the button.

**Expect**: with the feature off the button is disabled with a note and `GET $API/ai/status` says it is off; with it on, a Markdown body **appears piece by piece** in the body field while the button shows a Stop control (the title and tags are untouched), labelled as an AI proposal, and **nothing is saved or published** until you save; the article list is unchanged until then. Asking more often than the limit returns 429. The automated tests cover all of this with a fake model; a real call is a manual step because it needs a key and costs a few cents.

## Checking the automated tests cover the invariants

The test names are listed in `docs/nextjs-fastapi-architecture.html` (section 12.1). After `make test`, confirm there is at least one passing test for each of INV-001 to INV-006, including: a raw `UPDATE` on a snapshot rejected by the database, a failure injected at each step of Publish leaving nothing changed, two simultaneous Publish calls giving one 201 and one 409, the protected version refused for deletion, and Restore leaving every snapshot row identical.

## Where to check the deployed site

Assessors use the deployed site (the URL is in `README.md`; the Basic credentials are shared outside the repository). Run scenarios 1 to 10 in the browser. The deployment files are low priority and are not verified until they have been built and run.
