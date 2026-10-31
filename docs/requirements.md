# Northbeam Docs Studio Requirements

> Written in Canadian English. The Japanese version is in `docs/ja/requirements.md`. Keep the two in sync.

## 1. Purpose

- Build a content management service for internal writers (API plus a minimal UI) and a public site where only published articles can be read.
- The assessment centres on **data integrity and a correct lifecycle**.
- Get the core features right. Anything not implemented goes in the README, with "what is not implemented" and "how it would have been implemented".

## 2. Premises and terms

| Term | Meaning |
|---|---|
| Draft | The editable content held in the `draft_*` columns of an `articles` row. Not visible to the public side |
| Snapshot / version | An immutable record created at publish time (`article_versions`) |
| Live version | The version that `current_published_version_id` points to |
| State (status) | `draft` (**never published**) / `published` / `unpublished` (taken down) |
| Protected version | The version `current_published_version_id` points to, whatever the article's status (also after Unpublish). It cannot be deleted |

- The writer is a single user (protected by Basic authentication). The public side is unauthenticated general users.

## 3. Functional requirements

### 3.1 Writer side

| ID | Requirement |
|---|---|
| FR-1 | A writer can create an article. Input: title, slug, body (Markdown) and tags. If the slug is already taken, a numeric suffix is appended and the stored slug is returned (section 13, U15) |
| FR-2 | A writer can edit the draft of an existing article |
| FR-3 | **Publish**: a writer can publish the current draft (details in 3.3) |
| FR-4 | **Unpublish**: a writer can take an article down (details in 3.4) |
| FR-5 | The version history can be listed, newest first |
| FR-6 | The content of a specific version can be viewed |
| FR-7 | **Restore**: the content of a past version can be restored into the draft (details in 3.5) |
| FR-8 | A version that is not protected can be deleted. The API rejects deleting the protected version (details in 3.6) |
| FR-9 | When a draft is edited concurrently, overwriting with stale data is detected (details in INV-5 in section 4) |
| FR-13 | The writer side (the `/studio` screens and the writer API) is protected by **Basic authentication** when it is enabled. It is controlled by one explicit setting, `BASIC_AUTH_ENABLED`, which **must be on in production** and may be switched off only for a local run. Credentials come from environment variables (`BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD`) and are never written in code. When enabled, every writer route, including GET, checks authentication **before** any lookup or validation and returns 401 with `WWW-Authenticate: Basic` and the standard error envelope (code `unauthorized`). The service refuses to start if authentication is enabled and either credential is empty; in production it also refuses to start unless authentication is enabled; when it is off, start-up logs a clear warning. The public site, the public API (`/api/v1/public/*`) and `GET /healthz` need no authentication. Writer responses carry `Cache-Control: no-store`. `/docs` and `/openapi.json` are disabled in production. This is an addition beyond the assignment (section 13, R1 and R17) |
| FR-14 | A writer can list all articles (any status), showing the draft's title, slug, status, `draft_version` and `updated_at`, newest `updated_at` first (ties by `id` descending), at most 100 items, with an optional `status` filter (an unknown value returns 422) |
| FR-15 | The edit form shows a rendered Markdown preview that uses the same renderer and sanitization rules as the public site (U7) |
| FR-16 | On a `version_conflict` response, the edit form keeps the writer's unsent input, shows that the server copy has changed, and lets the writer either reload the latest version or resubmit their input against the new `draft_version` |
| FR-17 | **(Excluded from the planned scope; added only if time remains after everything else is done; section 13, R15.)** A writer can ask for an AI-generated draft from a topic, using the Claude API. The generated title, body and tags are returned to the edit form as a **proposal only**: nothing is saved until the writer saves it through the normal draft edit (with `expected_draft_version`), and nothing is published until the writer publishes. The feature is off unless `AI_ENABLED` is set, and it works only while the prepaid Claude API credit lasts |

### 3.2 Public side (unauthenticated)

| ID | Requirement |
|---|---|
| FR-10 | Published articles can be listed (only those: never-published and unpublished articles are not listed). Shown: title, tags and publication date (the first publication date, `published_at`). For a republished article (the live snapshot's `version_number` is 2 or more), also show the updated date (the creation time of the live snapshot). Order: `published_at` descending, then `id` descending. At most 100 items (`limit` / `offset`) |
| FR-11 | The detail of a published article can be viewed. **The content always comes from the current live snapshot**, never from the draft (title and tags too; even if the draft is edited after publishing, what readers see is what was last published). Public responses use a dedicated allow-list schema: slug, title, tags, body (detail only), `published_at` and the live snapshot's creation time. Never `draft_*`, `draft_version`, `articles.updated_at`, `status` or internal ids |
| FR-12 | Access to an article that was never published, an article that has been taken down, or a slug that does not exist (including one with an invalid format) returns the same **HTTP 404** with the same body. No error detail or draft content is shown |

### 3.3 Publish behaviour

Everything below happens in **one transaction**, in this order:

1. Lock the article row (`SELECT … FOR UPDATE`). If the article does not exist, return 404.
2. Compare the request's `expected_draft_version` (**required**: the version the writer was looking at) with `draft_version`. If they differ, return 409 `version_conflict` and change nothing (never publish a draft the writer did not see).
3. Check that the draft's title and body are non-empty. If not, return 422 `empty_content`.
4. **Idempotent check (U8):** if a live snapshot exists and the draft's title, body and tags equal it, create no snapshot and leave `published_at`, the pointer and `draft_version` unchanged. If the status was `unpublished`, set it back to `published`. Return 200 with the live version.
5. Otherwise create a **new immutable snapshot** from the draft, numbered from the article's own counter (`last_version_number + 1`; see section 13, R12), set status to `published`, point `current_published_version_id` at the new snapshot, set `published_at` **only if it is still empty** (first publication), and increment `draft_version`. Return 201 with the new version.

This includes setting `published_at`, so a row can never be published with an empty `published_at` (INV-2). Timestamps use the time of the statement (`clock_timestamp()`), not the start of the transaction, so a request that waited for the lock cannot get an earlier time than the previous version.

Order of checks for every writer request: authentication (401) → the article exists (404) → input shape and field validation (422) → `expected_draft_version` (409) → business rules (for example `empty_content` 422, `not_published` 409).

`draft_version` is incremented by an edit, by a Restore and by a Publish that creates a snapshot. It is not changed by Unpublish, Delete version or an idempotent Publish. Only edit, Restore and Publish require `expected_draft_version`; Unpublish and Delete version do not.

### 3.4 Unpublish behaviour

- Make the article invisible to the public side (set status to `unpublished`).
- **Do not delete** the last published snapshot. **Keep** `published_at` and the pointer.
- Only the status changes; the content and `draft_version` are not modified.
- If the article is not `published`, return 409 `not_published`.
- The request takes the article row lock, so a concurrent Publish and Unpublish are serialized and either order is a valid result.

### 3.5 Restore behaviour

- **Only copy** the title, body and tags of the chosen past snapshot into the current draft, in a single statement. The slug is not touched.
- Restore **never** changes `status`, `current_published_version_id` or `published_at`, whatever the article's status (never published, published or unpublished), and it does not publish.
- The request **must** include `expected_draft_version`. If it does not match, return 409. On success, increment `draft_version`.
- A version number the article does not have returns 404 and changes nothing.
- Do not create a new snapshot. Do not modify or delete existing snapshots.

### 3.6 Delete version behaviour

- The **protected version** is the version `current_published_version_id` points to, whatever the article's status, including after Unpublish. Every other version can be deleted.
- Deleting the protected version returns 409 `version_is_live`. A version number the article does not have returns 404. A successful delete returns 204.
- Delete takes the same article row lock as Publish, Unpublish and Restore, so a delete that races a Publish can never leave the pointer dangling or return a 500. The composite foreign key is the backstop; if it still fires (SQLSTATE 23503), it is mapped to the same 409.
- The live version is always the highest-numbered version and cannot be deleted, so an article's history is never empty once it has been published.
- `expected_draft_version` is not required.

## 4. Invariants (most important)

| ID | Invariant | What the tests confirm |
|---|---|---|
| INV-1 | A published snapshot never changes after publishing. Edits always go through the draft | Editing the draft after publishing changes neither the snapshot nor what the public side shows. No API updates a snapshot, **and a database trigger rejects any UPDATE on `article_versions`** (a test attempts a raw UPDATE and expects it to fail) |
| INV-2 | **Publish is atomic.** These inconsistencies never occur: published but nothing to point at / published but pointing at an old version / not published but a new live version is set. This holds through crashes and concurrent requests | Failure injection at each step of Publish (parametrized) rolls everything back: no new version row, and `status`, `current_published_version_id`, `published_at`, `draft_version` and `last_version_number` unchanged. Two simultaneous Publish calls with the same `expected_draft_version` (separate connections): exactly one returns 201 and the other 409, with no 5xx; version numbers stay contiguous and the pointer matches the newest version. A database CHECK rejects a hand-written UPDATE that sets `status='published'` with a NULL pointer or NULL `published_at` |
| INV-3 | The protected version (the one the pointer references, also while unpublished) cannot be deleted (hiding the button in the UI is not enough; the **API rejects it**) | Publish v1 → Unpublish → Delete v1 returns 409 `version_is_live` and the row still exists. Publish v2, then Delete v1 returns 204. A Delete racing a Publish never returns 5xx and never leaves the pointer dangling |
| INV-4 | Restore does not damage history. It never changes, creates or deletes a snapshot | Before and after Restore, **every column of every row** of `article_versions` for that article is identical, and `status`, `current_published_version_id` and `published_at` are unchanged; only the draft columns and `draft_version` change. Restoring a version number that does not exist returns 404 with no change |
| INV-5 | **Optimistic concurrency.** An update based on stale data is rejected with a clear error, and newer edits are never silently overwritten | An update with a stale `draft_version` returns 409 and changes nothing. `draft_version` increases with every successful edit, Restore or snapshot-creating Publish. An edit and a Restore with the same `expected_draft_version`: exactly one succeeds. A Publish whose `expected_draft_version` is older than a committed edit returns 409 and creates no snapshot |
| INV-6 | History survives unpublishing. The snapshots and `published_at` do not disappear | After Unpublish, the version list, the content and `published_at` all remain. Republishing leaves `published_at` at the first value |

Every invariant (INV-1 to INV-6) has at least one automated test, and `make test` runs all of them.

## 5. Constraints

| Item | Content |
|---|---|
| Technology | Languages and frameworks are free to choose |
| Persistence | A real database is required (**PostgreSQL is adopted**). In-memory only is not allowed. Data must survive a restart. Local runs use PostgreSQL started by Docker Compose; the database can also be chosen with `DATABASE_URL` (for example Cloud SQL through the Auth Proxy) |
| Running | From a fresh checkout, **`docker compose up --build` starts everything** (PostgreSQL, the schema, the API and the web app) and needs only Docker. `make setup`, `make dev` and `make test` run the project natively against the Compose databases or any PostgreSQL given by `DATABASE_URL`. Assessors may use this local run or the deployed Cloud Run site (section 13, U14) |
| Databases | Local development uses its own databases (`<name>_dev` and `<name>_test`) and never the production database. Tests read `TEST_DATABASE_URL` and, before any statement, abort unless the database name ends in `_test` and the host is `localhost` or `127.0.0.1` (never a `/cloudsql` socket). A unit test covers this guard. Tests reset the data between tests with a `TRUNCATE` inside a transaction that first runs `SET LOCAL docs.allow_reset = 'on'` (the only case the snapshot table's `TRUNCATE` guard allows), and concurrency tests use real separate connections (a pool of at least 2). `compose.yaml` provides both databases: `db` for development and `db-test` for tests |
| Tests | Automated tests are **mandatory**, not optional. They run with a single command (`make test`; on a machine with only Docker, `make test-docker`, which runs `docker compose --profile test run --rm test`), which runs the backend tests, the OpenAPI drift check, and the frontend type check, lint and Markdown sanitization tests. Each of INV-1 to INV-6 needs at least one automated test (section 4); an invariant without a test is a defect |
| What is tested | Lifecycle invariants for Publish / Unpublish / Restore / Delete / Concurrency. **These take priority over UI tests** |

## 6. Out of scope (not implemented)

Authentication, roles and multi-tenancy (note: Basic authentication on the writer side is added as an exception; section 13, R1) / rich Markdown extensions and WYSIWYG (a plain input and a preview are enough) / file and media uploads / search / large-scale pagination / a caching layer / production deployment / CI/CD / IaC.

> Deleting an article itself is also not implemented (section 13, U9).

> Production deployment, CI/CD and IaC are out of scope in the assignment. However, because the runtime platform is GCP Cloud Run, the necessary configuration files are provided (section 12). Their priority is below finishing the core features, and leaving them incomplete does not affect the assessment. The exception is the local `compose.yaml`: it is part of the short setup command and is finished before the README.

## 7. Minimal UI

An article edit form, an article list and a version history panel, plus the public list and detail pages.

The interface is **minimal and stylish, built with Tailwind CSS**: a neutral colour palette with one accent colour, a system font stack, generous whitespace, a small set of consistent shared components (buttons, inputs, tags, status badges, empty states), visible keyboard focus, and layouts that work from phone to desktop widths. Styling is a polish step done **after** the functionality and its tests, within a fixed time box, and it never delays the core features (looks are not assessed).

## 8. Deliverables

1. **Git repository**: working code, plus **a commit history that shows the specification was written before (or alongside) the implementation**. The first commits contain only the tooling (`.specify/`, `.claude/`, `CLAUDE.md`), `docs/` and `specs/001-docs-studio/` (`spec.md`, `plan.md`, `tasks.md`). Nothing under `backend/` or `frontend/` (code, the DDL in `db-automation-apply/`, the Dockerfiles, the YAML files) is committed before `spec.md`; only the `CLAUDE.md` files are exempt. Do not rewrite history (no squashing or rebasing).
   - **How to verify:** `git log --reverse --diff-filter=A --name-only --format='commit %h' -- specs/001-docs-studio/spec.md backend frontend ':(exclude)backend/CLAUDE.md' ':(exclude)frontend/CLAUDE.md'` lists the files in the order they were first added, and `specs/001-docs-studio/spec.md` must appear before any file under `backend/` or `frontend/`. A script, `scripts/check-spec-first.sh` (created in the tasks), runs this check and fails if the order is wrong.
2. **SDD artifacts**: `spec.md`, `plan.md` and `tasks.md` in `specs/001-docs-studio/`, following Spec Kit conventions.
   - spec: the requirements and invariants in your own words. It must cover these edge cases: Publish atomicity, protecting the live version from deletion, non-destructive restore and concurrent editing.
   - plan: the data model, API design and key design decisions such as optimistic concurrency.
   - tasks: the work broken down in implementation order.
3. **README.md**: starts with the assessor path (the deployed Cloud Run URL; the Basic authentication credentials are shared outside the repository), then how to run it locally / a description of the data model / why that model was chosen / a paragraph (at least) on a design trade-off made under the time limit / improvements if there were more time / a table of features with their status (done / partial / not done) and how each missing one would be built. It also states that the Cloud Run files are optional and were not verified as part of the assessed scope.
4. **Automated tests**: runnable with a single command.

## 9. Recommended data model (not mandatory)

`articles`: id, slug (unique), status (draft/published/unpublished), draft_title, draft_body, draft_tags, draft_version (for optimistic concurrency), current_published_version_id (nullable), published_at (nullable), created_at, updated_at

`article_versions`: id, article_id (foreign key), version_number (unique per article), title, body, tags, created_at

> The key point is to **never mix the draft and the published content in the same row**.

## 10. Optional extra features (at most one or two)

The two adopted are **3. Slug collision handling** (section 13, U15) and **4. Idempotent Publish** (section 13, U8). Save as Version and Diff View are not adopted.

1. Save as Version: save the draft as a version without publishing it
2. Diff View: compare the draft with a past version, or two versions with each other
3. Slug collision handling: when a slug is taken, append a number to make it unique
4. Idempotent Publish: when Publish is run again with no changes to the draft, do not create a duplicate snapshot with the same content

## 11. Points to settle before writing the spec (not stated in the assignment)

> Where section 13 (U1 to U15) has decided a point, the decision in section 13 takes priority over the "provisional approach" below.

| Topic | What the assignment says | Provisional approach (to be confirmed in spec/plan) |
|---|---|---|
| Error code for a stale update | Only says "a clear error" | 409 Conflict, returning the current `draft_version` |
| Unpublish → republish | Not stated | Allowed. Set status back to `published` and keep `published_at` |
| version_number after deleting a non-live version | Not stated | Numbers are **never reused**: a per-article counter column (`last_version_number`) is incremented under the row lock, so the guarantee does not depend on which versions exist (section 13, R12) |
| Can the previously live version be deleted while unpublished? | A version "referenced by a live article" cannot be deleted. What happens after unpublishing is not specified | The reference is kept (to honour INV-6, "the last published content stays viewable"), so deletion is **not allowed** |
| Publishing an article that was never published (status=draft) | Possible | Possible (this is the first publication) |
| Can the slug be changed? | Not stated | **Cannot be changed after creation** (U3). PATCH accepts no slug; an unknown field returns 422 |
| Slug collides with another article | A uniqueness constraint. Collision handling is an optional feature | Adopted (U15): append a numeric suffix and return the stored slug. 409 `slug_conflict` only if every retry loses a race |

### Decisions already made

| Topic | Decision |
|---|---|
| `draft_version` on Publish and Restore | **Required.** A mismatch returns 409 |
| Dates on the public side | Show the first publication date (`published_at`) by default. For a republished article, also show an updated date. The updated date uses the **creation time of the live snapshot** (`articles.updated_at` is not used, because it changes on every draft edit) |
| Authentication | **Basic authentication** on the writer side only (the assignment treats authentication as Out of Scope, but this is added to avoid letting anyone edit, publish or delete on the deployed site). Controlled by `BASIC_AUTH_ENABLED`: **required in production**, and **off by default for a local run** (section 13, R17). The public site and the public API need no authentication |
| Exposure of the API | The public API (`/api/v1/public/*`) is exposed **without authentication**. The writer API **requires Basic authentication**. No ID-token handling is implemented |

## 12. Runtime and deployment environment (adopted approach)

The assignment leaves technology choices open, so the following are adopted.

| Item | Adopted |
|---|---|
| Database | **PostgreSQL**: PostgreSQL 17 in Docker Compose for local runs (`db` for development, `db-test` for tests) and **Cloud SQL for PostgreSQL** in production. The target is switched with the `DATABASE_URL` environment variable |
| How to run locally | `docker compose up --build` (everything in containers), or natively with `make setup` and `make dev` against the Compose databases. To use Cloud SQL instead, relay it to `localhost` with the Cloud SQL Auth Proxy (`cloud-sql-proxy`, `gcloud auth application-default login`) and set `DATABASE_URL`. To be confirmed in `plan.md` |
| Runtime platform | **GCP Cloud Run** (the frontend `docs-studio-web` and the API `docs-studio-api` are deployed as separate services) |
| Migrations | Alembic. A Cloud Run Job runs `alembic upgrade head` at deploy time |
| DDL | The DDL is stored in `backend/db-automation-apply/` as numbered SQL files (`001_schema.sql`). How Alembic applies it is decided in `plan.md` |
| Exposure | The frontend (public site and writer screens) and the API are exposed on Cloud Run with `ENV=prod` and `BASIC_AUTH_ENABLED=true`. Only the writer side uses Basic authentication; the public site needs none |
| Secrets | Secret Manager (`database-url`, `basic-auth-user`, `basic-auth-password`) |
| Caching | None. Public pages are rendered dynamically on every request (`force-dynamic`), so an unpublish takes effect immediately. No cache layer (out of scope; section 13, R11) |
| Databases | Production, development and test databases are separate (section 5; section 13, R14) |
| Limits | `--max-instances` is set on both services. The API connection pool is sized against Cloud SQL's `max_connections` (for example `pool_size=3`, `max_overflow=2` with three instances). The migration Job uses `--max-retries=0` |
| AI draft generation (excluded; only if time remains) | The API calls the **Claude API** (Anthropic) with an API key kept in Secret Manager (`anthropic-api-key`, passed as `ANTHROPIC_API_KEY`; never in code or logs). Cost is capped by **prepaid credit**: only a fixed amount is deposited, so the feature stops working when the credit is used up. In the Anthropic Console, keep automatic reload off and set a workspace spend limit (to be confirmed when it is built). Settings: `AI_ENABLED` (off by default) and `ANTHROPIC_MODEL` (a small, inexpensive model, chosen and confirmed when it is built). Extra guards: input and output-token limits per request, a per-instance rate limit, and the instance cap. Tests never call the Claude API |

### Required YAML files

| File | Location | Status | Role |
|---|---|---|---|
| `compose.yaml` | repository root | To be created (tasks) | Local run: PostgreSQL 17 for development (`db`) and tests (`db-test`), plus `migrate`, `backend` and `frontend` services built from the Dockerfiles, so `docker compose up --build` runs everything. Part of the short setup command, so it is **not** low priority |
| `cloudbuild.yaml` | backend | Created | Build → Artifact Registry → migration Job → Cloud Run (api) |
| `cloudbuild.yaml` | frontend | Created | Build → Artifact Registry → Cloud Run (web) |

### Dockerfile

| File | Location | Status | Content |
|---|---|---|---|
| `Dockerfile` / `.dockerignore` | backend | Created (not yet built) | python:3.12-slim + uv. Dependency layer first, then src and alembic. Non-root, port 8000 |
| `Dockerfile` / `.dockerignore` | frontend | Created (not yet built) | Three-stage node:22-slim build (standalone output). Non-root, port 3000 |

- Docker is used for the local run: Docker Compose builds the same Dockerfiles. Cloud Build builds the production images on GCP.
- The Dockerfiles assume `pyproject.toml` / `uv.lock` (backend) and `package.json` / `pnpm-lock.yaml` plus `output: "standalone"` in `next.config.ts` (frontend). Verify the builds once these exist (add this to tasks).
- `_SQL_INSTANCE`, `_RUNTIME_SA` and `_API_URL` in `cloudbuild.yaml` are left blank. Specify them per environment.
- Creating Cloud SQL, Artifact Registry, Secret Manager and the service accounts is done by hand (IaC is out of scope).
- The API has no IAM authentication, so no ID-token handling is needed. To guard against heavy direct traffic, set an upper limit with Cloud Run's maximum instances.
- Basic authentication on the writer side is an addition beyond the assignment (section 13, R1). Its implementation priority is below the core features, but it must be in place before the deployed site is made public.
- Cloud Build's identity needs `roles/run.admin`, `roles/iam.serviceAccountUser` on the runtime service account, `roles/artifactregistry.writer` and `roles/logging.logWriter`, and the `run`, `sqladmin`, `secretmanager`, `artifactregistry` and `cloudbuild` APIs must be enabled. `--allow-unauthenticated` fails if an organization policy blocks `allUsers`. (To be confirmed when deploying.)
- The Cloud Run site and Cloud SQL must be running while the work is assessed, and the Basic authentication credentials are given to the assessor outside the repository.
- The Dockerfiles and YAML files have not been built or run yet. Do not describe them as verified until they have been (the Compose run verifies the Dockerfiles; Cloud Run is verified last).

## 13. Reconsidering the requirements (issues and resolutions)

We identified the points that would cause problems if the assignment were implemented as written, and the points the assignment does not spell out, and recorded the judgement for each along with its background. Every addition or change beyond the assignment has its rationale here. `spec.md` and `plan.md` follow these decisions.

- **R1 to R17**: points where the assignment's requirements were reconsidered and changed (issue and resolution)
- **U1 to U15**: points the assignment does not spell out, and what was decided (topic and decision)
- How to read the table: the "Background" column holds the **AS-IS** (what the assignment assumes, and how the issue arose), and the "Resolution / decision" column holds the **TO-BE** (the state after the decision).

| # | Background | Issue / topic | Resolution / decision | Reason / where reflected |
|---|---|---|---|---|
| R1 | **AS-IS:** The assignment treats authentication as Out of Scope and assumes a single trusted writer. We, however, deploy on Cloud Run, so that assumption does not hold. | The assignment says authentication is Out of Scope and is not assessed. But if the deployment is made public as it is, anyone can edit, publish and delete articles. Because the API is exposed on Cloud Run, protecting only the screens does not help if the API is called directly | **TO-BE:** **Add Basic authentication to the writer side only** (an addition beyond the assignment), switched by `BASIC_AUTH_ENABLED`: required in production, and off by default for a local run (R17). FastAPI's writer routes do the verification (the source of truth); Next.js forwards the `Authorization` header unchanged and, on a 401, returns it with `WWW-Authenticate` (so the browser shows its prompt). The ID and password are supplied through the environment variables `BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD` and never written in code (Secret Manager in production; local values go in `.env.example`). The public site and the public API stay unauthenticated. Comparison is constant-time (`secrets.compare_digest`). If time runs short, defer the implementation, but never deploy the writer side publicly without it | Reflected in: FR-13, section 12 |
| R2 | **AS-IS:** We chose Cloud Run as the runtime platform and made the frontend and API separate services. We considered making the API private (IAM authentication). | A private API (IAM authentication) would require the frontend server to attach an ID token. That is excessive for an assignment where authentication is out of scope, and behaviour would differ between local and production | **TO-BE:** The API does not use IAM authentication and is **exposed to the internet** (the public API unauthenticated, the writer API under Basic authentication). No ID-token handling is implemented, so the same code runs locally and in production. To guard against heavy direct traffic, set an upper limit with Cloud Run's maximum instances | Reflected in: section 12, `backend/cloudbuild.yaml` |
| R3 | **AS-IS:** While organizing the requirements, we noticed that the transaction scope for Publish (steps 1 to 4) did not include setting `published_at`. | The transaction scope for Publish was "steps 1 to 4", and setting `published_at` (step 5) was not included. If it ran in a separate transaction, the inconsistency "published but `published_at` is empty" could arise, violating INV-2 | **TO-BE:** The transaction covers **steps 1 to 5**, and `published_at` is set in the same transaction. A database CHECK constraint also enforces that a published row must have a pointer and `published_at` | Reflected in: 3.3, the database structure in the architecture document |
| R4 | **AS-IS:** Only the detection of concurrent draft edits is required, but Publish and Restore can also be run from a stale screen. | It is unclear whether the assignment assumes Publish and Restore act on "the draft the writer was looking at". Publishing from a stale screen could publish a draft someone else has since changed, and Restore could overwrite it | **TO-BE:** Make `expected_draft_version` **required** on Publish and Restore. If it does not match the database, reject with 409 and create nothing. On success, increment `draft_version` | Reflected in: 3.3, 3.5 |
| R5 | **AS-IS:** The assignment only says to show a "publication date" in the list. There is also a requirement to keep `published_at` at the first value on republication, which clashes with the wish to show that an update happened. | It is unclear whether the "publication date" is the first or the latest publication date. The requirement not to change `published_at` on republication and the wish to show that an update happened cannot both be met | **TO-BE:** Show the **first publication date (`published_at`)**, and for a republished article also show an **updated date**. The updated date uses the **creation time of the live snapshot**. `articles.updated_at` is not used, because it changes on every draft edit and would leak draft activity to the public side | Reflected in: FR-10 |
| R6 | **AS-IS:** The assignment puts production deployment, CI/CD and IaC out of scope, but we chose Cloud Run as the runtime platform, so configuration files became necessary. | The assignment puts production deployment, CI/CD and IaC out of scope, but choosing Cloud Run as the runtime platform makes configuration files necessary | **TO-BE:** Provide `cloudbuild.yaml` and `Dockerfile`, but **at a priority below finishing the core features**. Leaving them incomplete does not affect the assessment. Creating Cloud SQL and similar resources is done by hand (IaC is out of scope) | Reflected in: sections 6 and 12 |
| R7 | **AS-IS:** We wanted local development to connect directly to Cloud SQL without Docker. The assignment, on the other hand, requires that the project can be run from a fresh checkout with a short setup command. | Without Docker, an assessor must install and configure a PostgreSQL before anything runs, which is weaker than the assignment asks; and tests that touch a shared database can destroy data used in development | **TO-BE:** Provide a root **`compose.yaml`** (PostgreSQL 17 for development and for tests, the migrations, the API and the web app) so that `docker compose up --build` runs everything from a fresh checkout with only Docker installed. Tests use a dedicated database only (a name ending in `_test`) and refuse to run against anything else. The database is still chosen by `DATABASE_URL` and `TEST_DATABASE_URL`, so Cloud SQL through the Auth Proxy still works. Cloud Run remains an equally valid place to assess (see U14) | Reflected in: sections 5 and 12 |
| R8 | **AS-IS:** The assignment does not define behaviour in detail, so some points vary from one implementer to the next. | Behaviour the assignment does not cover (deleting a version while unpublished, republishing, gaps in numbering, and so on) varies by implementer | **TO-BE:** Provisional approaches were decided and recorded in section 11 (the reference is kept while unpublished, so the version **cannot be deleted**; version_number is **never reused**; a stale update returns 409; and so on) | Reflected in: section 11 |
| R9 | **AS-IS:** The assignment says the live version cannot be deleted and that Unpublish keeps the last snapshot. Read together, the version an unpublished article still points to is protected too, and a delete can race a Publish. | "Live version" is ambiguous after Unpublish, and a Delete that races a Publish could leave a dangling pointer or surface a 500 | **TO-BE:** Define the **protected version** as the version the pointer references, whatever the status. Delete takes the same article row lock as Publish, returns 409 `version_is_live` for the protected version, and maps a foreign-key violation to the same 409 | Reflected in: 3.6, INV-3 |
| R10 | **AS-IS:** The first design said the frontend "forwards the Authorization header". A Server Action has no Authorization header of its own, and it cannot return `WWW-Authenticate`. | Basic authentication would not work through Server Actions as first described | **TO-BE:** Server Actions read the incoming header with `headers()` and pass it to the API on every call. When the API answers 401, the action surfaces it, and a route handler (not the action) returns `401` with `WWW-Authenticate: Basic` so the browser prompts again. Basic authentication has no logout, which is accepted. FastAPI stays the only validator | Reflected in: FR-13, architecture section 5 |
| R11 | **AS-IS:** The assignment puts a caching layer out of scope, and requires an unpublished article to return 404 to the public. | Any page or data cache could keep serving an unpublished article | **TO-BE:** No caching. Public pages are rendered dynamically on every request, and the public API sends no long-lived cache headers | Reflected in: section 12, architecture section 5 |
| R12 | **AS-IS:** The first design computed the next version number as `MAX(version_number) + 1`, which only avoids reusing numbers by accident (the highest version happens to be undeletable). | Numbers could be reused if a non-live version could ever be the highest (for example once Save as Version exists) | **TO-BE:** A per-article counter column, `last_version_number`, incremented under the row lock | Reflected in: architecture sections 7 and 9 |
| R13 | **AS-IS:** The first CHECK constraint accepts a `published` row being changed back to `draft` if the pointer and `published_at` are cleared in one UPDATE, which would destroy history (INV-6). | The database did not enforce INV-6, and atomicity comes from the transaction rather than from the constraints | **TO-BE:** A BEFORE UPDATE trigger on `articles` forbids clearing the pointer or `published_at`, moving the pointer backwards, and returning to `draft`. The architecture document describes what the constraints and the trigger each guarantee | Reflected in: architecture section 7 |
| R14 | **AS-IS:** Local development and production both use Cloud SQL, and the documents did not say they are separate. | Running `make setup` or the tests against the production database would corrupt the live site | **TO-BE:** Separate databases for production, development and test. Tests read `TEST_DATABASE_URL` and refuse to run unless the name ends in `_test` and the host is local; the guard has its own test | Reflected in: sections 5 and 12 |
| R15 | **AS-IS:** The assignment has no AI feature. We would like to generate articles automatically with AI. Calling Vertex AI from Cloud Run was considered, but a service that can be called without limit could run up an unbounded bill. | Whether to add AI generation, and how to do so without unbounded cost and without endangering the core lifecycle, the tests or the time budget if time remains | **TO-BE:** **Exclude it from the planned implementation.** It is recorded (FR-17) so that it can be added **only if time remains** after the core features, the invariant tests, the README and the adopted optional features are all done; it is not part of the plan, the tasks or the assessed scope. If it is built, it uses the **Claude API with prepaid credit** instead of Vertex AI, so the total spend can never exceed the amount deposited. Design constraints: (1) `POST /api/v1/ai/draft` is a writer route (Basic authentication) that returns `{title, body, tags}` and **writes nothing**; the writer reviews it and saves through the normal edit with `expected_draft_version`, so INV-1 to INV-6 are untouched and nothing is published automatically. (2) Output is normalized like any input (U4, U5) and rendered through the same sanitizer (U7). (3) The Claude client sits behind a small interface; tests use a fake and never call the API, so `make test` needs no key and costs nothing. (4) Off by default (`AI_ENABLED`); the API key comes from Secret Manager and is never logged; a timeout (30 s), input-length and output-token limits and a per-instance rate limit; when the credit is used up or the API fails, the route returns `503 ai_unavailable` (and `504 ai_timeout` on a timeout). (5) The UI labels the result "AI draft: review before publishing". (6) The README states that it is an extra beyond the assignment's list and, if it is not built, lists it as not implemented with this plan | A prepaid balance is a hard spending cap that a pay-as-you-go cloud service does not give. It is also feasible and useful, but outside the assessed scope and beyond the "at most one or two" optional features, so it must not compete with the core work for time | Reflected in: FR-17, section 12, architecture sections 10 and 11 |
| R16 | **AS-IS:** The assignment asks only for a minimal interface and says looks are only a tie-breaker. We still want it to look clean. | How polished the interface should be, and with what, without spending time the core needs | **TO-BE:** Style the interface with **Tailwind CSS** so it is **minimal and stylish**: a neutral palette with one accent colour, a system font stack, generous whitespace, a few small shared components, visible keyboard focus, and layouts that work from phone to desktop widths. No component library. Styling is a **time-boxed polish step done after the functionality and its tests**, and it never delays the core features | Tailwind gives consistent styling with little code and no separate design system; the time box protects the assessed work | Reflected in: section 7, spec FR-038, plan, research R-19 |
| R17 | **AS-IS:** The assignment says the writer side needs no authentication ("a single trusted user"). We added Basic authentication to protect the deployed, internet-facing site. | If it is always on, an assessor who calls the writer API without credentials (for example a script that follows the assignment, which needs none) gets 401s and may think the project is broken | **TO-BE:** One explicit setting, `BASIC_AUTH_ENABLED`. In production it **must** be on (the service refuses to start otherwise, and also if either credential is empty). For a local run (`ENV` is not `prod`) it **may be off, and the example environment file turns it off**, so `docker compose up --build` needs no sign-in and the assignment's "no authentication" holds; start-up logs a clear warning when it is off. It is an explicit setting, never an implicit fallback (unset credentials with the switch on is an error). The route-sweep test runs with authentication enabled | The deployed site stays protected, while a fresh local run behaves exactly as the assignment describes | Reflected in: FR-13, constitution principle IV, spec FR-028 to FR-031 |
| U1 | **AS-IS:** The assignment only says to return "a clear error" for a stale update. | Error format for a stale update | **TO-BE:** **409 Conflict**. The error code is `version_conflict`, and `details` carries the current `draft_version`. The client sends `expected_draft_version` in the request body (`If-Match` is not used) | The screen can prompt the user to reload and merge. A body field is simpler to implement and test than a header |
| U2 | **AS-IS:** The assignment describes how Unpublish works but not what happens when it is run on an article that is not live. | When Unpublish is run on an article that is not live | **TO-BE:** Reject with **409** (code `not_published`) | Making it idempotent would hide whether the call had any effect. This keeps the state transitions strict |
| U3 | **AS-IS:** The slug is only described as a "unique URL identifier", so the allowed characters, length and whether it can change are unclear. | Slug rules and changes | **TO-BE:** Lowercase letters, digits and hyphens only (`^[a-z0-9]+(-[a-z0-9]+)*$`), 1 to 100 characters, unique. **Cannot be changed after creation** | The public URL never changes, and history and external links do not break |
| U4 | **AS-IS:** Tags are only listed as an input field, with no rules. | Tag rules | **TO-BE:** At most 10 tags, each 1 to 30 characters. Trim surrounding whitespace, **normalize to lowercase**, and drop duplicates (keeping order) | Keeps the list display and the data free of variations |
| U5 | **AS-IS:** The lengths of title and body, and how empty values are treated, are unclear. | Length and emptiness of title / body | **TO-BE:** Title is 1 to 200 characters (whitespace only is not allowed). Body is at most 100,000 characters. **A draft may have an empty body**, but **Publish requires both title and body to be non-empty** (422, code `empty_content`) | Lets writers save work in progress while stopping an empty article from being published |
| U6 | **AS-IS:** The sort order of the public list is not stated. | Sort order of the public list | **TO-BE:** **Newest first by first publication date (`published_at`)**. Ties are broken by `id`, descending | The order is the same every time |
| U7 | **AS-IS:** The body is Markdown and is shown as HTML on the public site. Rendering the input as it is could allow XSS. | XSS protection when converting Markdown to HTML | **TO-BE:** **Raw HTML is not rendered** (sanitized). Links are limited to `http`, `https` and `mailto` | The body is typed in by writers, but readers of the public site must be protected |
| U8 | **AS-IS:** The assignment lets us pick at most two of four optional features. | Which optional features to adopt (at most two), and the exact rules of the one adopted | **TO-BE:** Adopt **Idempotent Publish**. It compares the draft's title, body and tags (tags as an ordered list) with the **live snapshot only**; a draft equal to an older version still creates a new version. If equal, no snapshot is created and `published_at`, the pointer and `draft_version` stay unchanged; if the status was `unpublished`, it is set back to `published`. The response is 200 (a new snapshot returns 201). The order of checks is `expected_draft_version` (409), then `empty_content` (422), then the idempotent check. Of the other three, Slug Collision Handling is also adopted (U15); Save as Version and Diff View are not | It ties directly to the integrity requirements and is easy to test. Save as Version would change what a "version that is not live" means and add complexity |
| U9 | **AS-IS:** The assignment does not mention deleting an article itself. | Deleting an article itself | **TO-BE:** **Out of scope.** Not implemented | Not in the assignment, and consistent with the policy of keeping history |
| U10 | **AS-IS:** The recommended data model has both `id` and `slug`, but does not say which one the API looks up by. | ID format and how articles are looked up | **TO-BE:** The ID is a `bigint` (auto-numbered). The writer API looks up by `id`, and the public API by `slug` | Even if the slug is not changed later, `id` is the most reliable key for the writer side. The public side needs the slug in the URL |
| U11 | **AS-IS:** Restore returns a snapshot to the draft, but the snapshot in the recommended data model has no slug. | Whether Restore copies the slug | **TO-BE:** **Do not copy it.** Restore only the title, body and tags into the draft | Because the design keeps no slug in the snapshot |
| U12 | **AS-IS:** The assignment asks for a "short setup command" and a "single-command test run", but does not give concrete commands or say how to reproduce concurrent Publish and a crash. | How to set up and test | **TO-BE:** Setup is `make setup` (install dependencies and run migrations), start is `make dev`, and tests are `make test`. Tests use the dedicated database only. **Concurrent Publish** is checked by sending two requests at once with `asyncio.gather`. **Atomicity under a crash** is checked by injecting an exception after the second SQL statement in the service and confirming that everything rolls back | Satisfies the assignment's "single-command tests" and lets INV-2 be verified |
| U13 | **AS-IS:** "Draft" is used with two meanings: the `draft_*` columns and `status=draft`. | The two meanings of "draft" | **TO-BE:** "Draft" refers only to the content of the `draft_*` columns of `articles`. An article with `status=draft` is called **never published**. ("Unpublished" is reserved for the taken-down status.) | Keeps the two meanings from being mixed up (already reflected in the terms table in section 2) |
| U14 | **AS-IS:** Assessors cannot reach our Cloud SQL, and the assignment expects the project to run from a fresh checkout. | How assessors check the work | **TO-BE:** **A `compose.yaml` is provided.** The README gives both ways: `docker compose up --build` on their own machine (needs only Docker), and the deployed Cloud Run site (the URL and the Basic authentication credentials are shared outside the repository, and the site and Cloud SQL stay running during the assessment). Either is a valid way to assess | Docker Compose satisfies "a short setup command from a fresh checkout"; the deployed site needs nothing installed at all |
| U15 | **AS-IS:** The assignment lists Slug Collision Handling as an optional feature (at most two may be adopted); without it, a taken slug is simply an error. | What happens when a new article's slug is already taken | **TO-BE:** Adopt **Slug Collision Handling** as the second optional feature. On create, if the slug is taken, append `-2`, `-3`, … (the smallest free number) and return the slug actually stored; the base is shortened when needed so the result stays within 100 characters. Concurrent creates that race for the same slug retry on the unique violation (up to 5 attempts), so each gets a distinct slug and none gets a 500; only if every attempt loses does the API return 409 `slug_conflict`. The slug still cannot be changed after creation (U3) | Makes creating articles forgiving without weakening uniqueness: the unique constraint stays the guarantee |

## 14. Assessment map (where each assessed point is specified and verified)

| Assessed point (from the assignment) | Where it is specified | How it is verified |
|---|---|---|
| Spec restates the functional requirements and invariants | Sections 3 and 4 | `specs/001-docs-studio/spec.md` (Spec Kit) |
| Edge case: Publish atomicity | 3.3, INV-2, R3, R12, R13; architecture sections 7 and 9 | Failure injection at each step; concurrent Publish; CHECK and trigger tests (architecture 12.1) |
| Edge case: the live version cannot be deleted | 3.6, INV-3, R9 | Delete tests, including after Unpublish and racing a Publish |
| Edge case: non-destructive Restore | 3.5, INV-4 | Every row of `article_versions` compared before and after |
| Edge case: concurrent editing | 3.3, INV-5, R4, U1 | Stale edit, stale Publish, edit versus Restore |
| Plan: data model | Section 9, architecture section 7, `backend/db-automation-apply/001_schema.sql` | Constraint and trigger tests |
| Plan: API design | Architecture section 10 | API tests |
| Plan: optimistic concurrency and other key decisions | Section 13, architecture sections 8 and 9 | `plan.md` records each decision |
| Tasks: work sequenced in order | Architecture 12.2 | `tasks.md` |
| Git history shows the spec came first | Section 8, item 1 | `scripts/check-spec-first.sh` |
| Automated tests for Publish, Unpublish, Restore, Delete, Concurrency | Sections 4 and 5; architecture 12.1 | `make test` |
| Runs locally with a short command | Section 5 (Running, Databases), U12, U14 | `docker compose up --build` (or `make setup` and `make dev`); or the deployed site |
| README contents and the unimplemented-features rule | Sections 1 and 8, item 3 | README review |
| Optional features (at most two) | Section 10, U8, U15 | Tests for Idempotent Publish and slug collision handling |

Most of the detail in this document goes to the points the assessment cares about: the lifecycle operations (3), the invariants (4), the tests (5) and the decisions (13). Deployment (12) is deliberately kept short and lower in priority, and the AI feature (FR-17) is excluded from the plan.
