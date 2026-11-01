# Northbeam Docs Studio

A content management service for internal writers (an API plus a minimal UI) and a public documentation site where only published articles can be read. Everything lives in one repository.

| Folder | Contents |
|---|---|
| `backend/` | FastAPI (src layout) and PostgreSQL. Details in `backend/CLAUDE.md` |
| `frontend/` | Next.js 16 (App Router). Details in `frontend/CLAUDE.md` |
| `docs/` | Requirements and architecture, shared by the frontend and backend. Canadian English; the Japanese versions are in `docs/ja/` |
| `specs/` | Spec Kit artifacts: `specs/001-docs-studio/` holds `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` and `tasks.md` |
| `README.md` | For assessors: the deployed address, how to run it, the data model and why, trade-offs, and a table of feature status |

The rules of this project are in `.specify/memory/constitution.md`. Read it first.

## Language policy
- **Everything outside `docs/ja/` MUST be written in Canadian English** (for example behaviour, colour, grey, defence, organize, analyze): the documents in `docs/`, the specs, the README, code, comments in code and configuration files, and the `CLAUDE.md` files.
- **Japanese appears only in `docs/ja/`.** Every document in `docs/` has a Japanese version with the same file name in `docs/ja/`. When the English version changes, update the Japanese version in the same change; never change only one.
- The Japanese versions of the `CLAUDE.md` files are `docs/ja/claude-root.md`, `docs/ja/claude-backend.md` and `docs/ja/claude-frontend.md`.
- Checks: `ls docs docs/ja` (the same file names are present) and `grep -rlP "[\x{3040}-\x{30ff}\x{4e00}-\x{9fff}]" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=ja .` (it must print nothing).
- Proper names (such as Northbeam Docs Studio) may appear in text but MUST NOT be used in folder or file names.

## Reference documents (`docs/`)
Read the relevant ones before working. If `docs/` and `specs/` disagree, `specs/` is the confirmed specification: follow it and correct `docs/`.

| File | Contents | When to read it |
|---|---|---|
| `docs/requirements.md` (Japanese: `docs/ja/requirements.md`) | The requirements extracted from the assignment: functional requirements FR, invariants INV, constraints, deliverables, and every decision (section 13) | As the input of `/speckit-specify`; to check the basis of a rule or a test |
| `docs/nextjs-fastapi-architecture.html` (Japanese: `docs/ja/`) | Diagrams of the structure, the layers, the database (DDL and ER diagram), state transitions, the API draft, the Cloud Run layout, the test plan | For `/speckit-plan`, implementation and database work |

## How work is done: Spec Kit (specification first)
For a new feature or a large change, work in this order and commit each stage's artifacts before the next, so the history shows the specification came before the implementation.
1. `/speckit-constitution`: the project's principles (once)
2. `/speckit-specify`: `spec.md` (requirements, invariants, edge cases)
3. `/speckit-clarify` (optional): find ambiguities
4. `/speckit-plan`: `plan.md` and the design artifacts (data model, API shape, decisions such as how optimistic concurrency works)
5. `/speckit-tasks`: `tasks.md` (tasks in build order)
6. `/speckit-analyze` (optional): consistency check of the three artifacts
7. `/speckit-implement`: implement following `tasks.md`

- **Order of the first commits**: (1) the tooling (`.specify/`, `.claude/`, `CLAUDE.md`, `.gitignore`), `docs/`, `README.md` and `specs/001-docs-studio/` together, (2) everything else (the DDL, Dockerfiles, YAML and code under `backend/` and `frontend/`). Do not commit anything under `backend/` or `frontend/` (except their `CLAUDE.md` files) before `spec.md`. `scripts/check-spec-first.sh` (task T002) verifies this.
- If the specification has to change during implementation, update the spec, plan and tasks before the code.
- Never rewrite history (no squashing, rebasing or force-pushing).
- When the API changes, update `backend/openapi.json` and regenerate the `frontend` types.
- A small fix or a bug fix does not need a spec.

## Running locally (Docker Compose)
From a fresh checkout, `cp .env.example .env` and `docker compose up --build` start the whole system (PostgreSQL, the schema, the API and the web app) and need only Docker. `make setup`, `make dev` and `make test` run it natively against the Compose databases or any PostgreSQL given by `DATABASE_URL`. `make test-docker` runs the backend tests in a container with only Docker. The writer login is off by default for a local run (`BASIC_AUTH_ENABLED`; always on in production). The root `compose.yaml` is part of the short setup command, so it is not low priority.

## Deployment (GCP Cloud Run)
Low priority. It was built and deployed once by hand (2026-11-01); the writer scenarios were not run on the deployed site. Each service is built from its own folder, which has a `Dockerfile` and a `cloudbuild.yaml`.

```bash
gcloud builds submit backend --config backend/cloudbuild.yaml
gcloud builds submit frontend --config frontend/cloudbuild.yaml
```
