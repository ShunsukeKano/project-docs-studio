# Docs Studio Constitution

## Core Principles

### I. Data Integrity First (NON-NEGOTIABLE)
- A draft and published content MUST NOT share a row. The draft lives in the `draft_*` columns of
  `articles`; published content lives in `article_versions`.
- A snapshot MUST be immutable. The database MUST reject every UPDATE on `article_versions`
  (trigger), and TRUNCATE is guarded separately.
- Publish MUST be one atomic transaction: lock the article row, check `expected_draft_version`,
  then create the snapshot, move the pointer, set the status and set `published_at` (first
  publication only). A Publish that fails at any step MUST change nothing.
- The protected version (the version `current_published_version_id` points to, also after
  Unpublish) MUST NOT be deletable. The API rejects it with 409 `version_is_live`, and the
  composite foreign key is the backstop.
- Restore MUST only copy a snapshot's title, body and tags into the draft. It MUST NOT create,
  change or delete a snapshot, and it MUST NOT change `status`, the pointer or `published_at`.
- Concurrent edits MUST be detected by optimistic concurrency. Edit, Restore and Publish require
  `expected_draft_version`; a stale value returns 409 and changes nothing.

Rationale: data integrity and a correct lifecycle are what the work is assessed on, and each rule
above guards one of the six invariants (INV-1 to INV-6).

### II. Specification Before Implementation
- `spec.md`, `plan.md` and `tasks.md` in `specs/001-docs-studio/` MUST be committed before any file
  under `backend/` or `frontend/` (only the `CLAUDE.md` files are exempt).
- Git history MUST NOT be rewritten: no squashing, rebasing or force-pushing of existing commits.
- `scripts/check-spec-first.sh` MUST verify this order and MUST pass before submission.
- When the specification has to change during implementation, `spec.md`, `plan.md` and `tasks.md`
  MUST be updated before the code.

Rationale: the assessed discipline is that the specification came first, and history is the
evidence.

### III. Tests Are Mandatory and Come Before UI (NON-NEGOTIABLE)
- Every invariant INV-1 to INV-6 MUST have at least one automated test. An invariant without a
  test is a defect.
- Tests MUST run against a real PostgreSQL `_test` database. Database guarantees MUST NOT be
  tested with mocks.
- Tests MUST refuse to run, before executing any statement, unless the database name ends in
  `_test` and the host is `localhost` or `127.0.0.1`. A unit test covers this guard.
- `make test` MUST run everything with a single command: the backend tests, the OpenAPI drift
  check, and the frontend type check, lint and Markdown sanitization tests.
- For each invariant, the failing test MUST be written before the code that satisfies it, and the
  invariants MUST be finished before the UI and the deployment files are started.
- Concurrency tests MUST use real, separate database connections.

Rationale: the invariants live in the database, and the assessment weighs these tests above UI
tests.

### IV. Secure by Default
- Writer routes MUST sit behind a router-level Basic authentication dependency, switched by the
  explicit setting `BASIC_AUTH_ENABLED`. The switch MUST be on in production, and MAY be off only for
  a local run (`ENV` is not `prod`), where start-up logs a warning. Public routes
  (`/api/v1/public/*` and `/healthz`) MUST NOT be behind it.
- Authentication MUST be checked before any lookup or validation: 401 comes before 404 and 422.
- Credentials MUST come from environment variables only (`BASIC_AUTH_USER`,
  `BASIC_AUTH_PASSWORD`). They MUST NOT be written in code or logged, MUST be compared in constant
  time. The application MUST refuse to start if authentication is enabled and either is empty, and
  in production it MUST refuse to start unless authentication is enabled. `/docs` and
  `/openapi.json` MUST be disabled in production.
- Public responses MUST use a dedicated allow-list schema and MUST NOT expose `draft_*`,
  `draft_version`, `articles.updated_at`, `status` or internal ids. A never-published article, an
  unpublished article and a missing slug MUST return the same 404.
- A test MUST walk every route, with authentication enabled, and fail if a writer route can be
  reached without credentials.

Rationale: the API is exposed on Cloud Run, so protecting only the screens would not protect the
writer API. The assignment says writers need no sign-in, so a local run may turn it off; the
deployed, internet-facing service may not.

### V. Simplicity and Scope
- The core lifecycle MUST be finished first. The only optional features adopted are Idempotent
  Publish and Slug collision handling.
- AI draft generation (FR-17) is excluded from the plan. If it is ever built, it MUST use the Claude API
  with prepaid credit, so spending is capped by the amount deposited. It MAY be added only after
  everything else is complete, and it MUST NOT write anything by itself.
- The Cloud Run files (`cloudbuild.yaml`) are low priority. They MUST NOT delay the core features or
  the tests, and neither they nor the Dockerfiles may be described as verified until they have been
  built and run. The local `compose.yaml` is the exception: it is part of the short setup command, so
  it MUST be finished before the README.
- Items the assignment puts out of scope (rich Markdown extensions, uploads, search, large-scale
  pagination, a caching layer, IaC, CI/CD) MUST NOT be built.
- If time runs short, stop adding features, finish the invariants and their tests, and list what
  is not done, and how it would be built, in the README.

Rationale: the assignment prefers a correct core over half-finished extras.

### VI. Language and Documentation
- Everything outside `docs/ja/` MUST be written in Canadian English: the documents in `docs/`, the
  specs, the README, code, comments in code and configuration files, and the `CLAUDE.md` files.
  Japanese MUST appear only in `docs/ja/`.
- Every document in `docs/` MUST have a Japanese version with the same file name in `docs/ja/`,
  and the two MUST be updated in the same change. The Japanese versions of the `CLAUDE.md` files are
  `docs/ja/claude-root.md`, `docs/ja/claude-backend.md` and `docs/ja/claude-frontend.md`.
- Proper names such as Northbeam Docs Studio MAY appear in text but MUST NOT be used in folder or
  file names.
- If `docs/` and `specs/` disagree, `specs/` wins and `docs/` MUST be corrected.

Rationale: one working language keeps the specification consistent, and the Japanese twins keep it
readable for the whole team.

### VII. No Caching, Dynamic Public Pages
- Public pages MUST be rendered dynamically on every request (`force-dynamic`, and `no-store` on
  the API fetch). No cache layer is built.
- An unpublish MUST take effect on the next request.
- Writer responses MUST carry `Cache-Control: no-store`, and the public API MUST NOT send
  long-lived cache headers.

Rationale: a stale cached page would break the requirement that an unpublished article returns 404,
and a caching layer is out of scope.

## Additional Constraints
- Stack: Next.js 16 (App Router) frontend; FastAPI with SQLAlchemy 2.0 (async) and Alembic backend;
  PostgreSQL (Docker Compose for local runs, Cloud SQL in production); GCP Cloud Run for deployment.
- From a fresh checkout, `docker compose up --build` MUST start the whole system, needing only
  Docker. The application can also run natively (`make setup`, `make dev`, `make test`).
- The DDL is stored in `backend/db-automation-apply/` as numbered SQL files and is the source of
  truth for the data model. An applied file MUST NOT be edited; a change is a new numbered file.
- Production, development (`<name>_dev`) and test (`<name>_test`) databases MUST be separate.
- OpenAPI is the only contract between the frontend and the backend. Frontend types are generated,
  never hand-written, and `make check-api` MUST fail if they are out of date.
- Layering: Router (HTTP only) -> Service (business rules and the transaction; the only layer that
  commits; the tests target it) -> Repository (thin, optional). A Service MUST NOT raise
  HTTPException.
- Every writer operation MUST take the article row lock first (or be a single conditional UPDATE)
  and decide against the locked row. The lock order is always the article row, then version rows.
- Errors MUST use the uniform envelope `{ "error": { "code", "message", "details" } }`.

## Development Workflow
- Spec Kit order: constitution, specify, clarify (optional), plan, tasks, analyze (optional),
  implement.
- The first commit holds the tooling, `docs/` and `specs/001-docs-studio/` together (or two commits
  in that order); everything else (code, the DDL, Dockerfiles, YAML) comes after.
- Build order: schema and its constraint tests; the service lifecycle one invariant at a time, test
  first; the writer API, then the public API; the minimal UI; the README; then Cloud Run.
- Quality gates before submission: `make test` passes; `scripts/check-spec-first.sh` passes;
  `docs/` and `docs/ja/` are in sync; the README starts with the assessor path (the deployed URL),
  and includes how to run it, the data model and why it was chosen, at least one design trade-off,
  improvements with more time, and a table of features with their status.

## Governance
- This constitution supersedes other practices in this repository.
- An amendment MUST state its reason, MUST bump the version, and MUST be committed together with
  any documents it makes out of date. Versioning follows semantic versioning: MAJOR removes or
  redefines a principle, MINOR adds or materially expands one, PATCH clarifies wording.
- Compliance review: every specification, plan and task list MUST be checked against these
  principles (the Constitution Check in `plan.md`). A violation MUST be fixed or justified in the
  plan's complexity tracking.
- Runtime guidance lives in the `CLAUDE.md` files and in `docs/`.

**Version**: 1.0.0 | **Ratified**: 2026-10-31 | **Last Amended**: 2026-10-31
