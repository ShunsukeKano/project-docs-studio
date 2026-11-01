# Docs Studio: single-command entry points.
# Local values come from .env (copy .env.example to .env). Nothing secret is committed.

ifneq (,$(wildcard .env))
include .env
export
endif

COMPOSE ?= docker compose

.PHONY: help setup dev test test-docker e2e check-api check-spec-first db-up db-down

help:
	@echo "make setup            install dependencies, start the Compose databases, apply the schema"
	@echo "make dev              start the API (and the web app once it exists)"
	@echo "make test             run every test (needs TEST_DATABASE_URL, a local database ending in _test)"
	@echo "make test-docker      run the backend tests in a container (needs only Docker)"
	@echo "make e2e             drive the screens in a real browser against a throwaway Docker system (needs Docker and Chrome)"
	@echo "make check-api        regenerate openapi.json and the frontend types; fail on any difference"
	@echo "make check-spec-first verify spec.md was committed before any backend/ or frontend/ file"

# Start the Compose databases (development and test) unless DATABASE_URL points at another host.
# A local URL (as in .env.example) counts as "ours", so the Compose database is started for it.
db-up:
	@case "$$DATABASE_URL" in \
		""|*@localhost[:/]*|*@127.0.0.1[:/]*) START=1 ;; \
		*) START=0 ;; \
	esac; \
	if [ "$$START" = 1 ]; then \
		echo "starting the Compose databases"; \
		$(COMPOSE) up -d --wait db; \
		$(COMPOSE) --profile test up -d --wait db-test; \
	else \
		echo "DATABASE_URL is set: using that database"; \
	fi

db-down:
	$(COMPOSE) --profile test down

setup: db-up
	cd backend && uv sync
	@if [ -f frontend/package.json ]; then \
		cd frontend && pnpm install; \
	else \
		echo "frontend skeleton does not exist yet: skipping pnpm install"; \
	fi
	cd backend && uv run alembic upgrade head

dev:
	@echo "API on http://localhost:8000, web app on http://localhost:3000"
	@trap 'kill 0' INT TERM; \
	(cd backend && uv run uvicorn app.main:app --reload --app-dir src --port 8000) & \
	(cd frontend && pnpm dev) & \
	wait

test:
	@case "$$TEST_DATABASE_URL" in \
		""|*@localhost[:/]*|*@127.0.0.1[:/]*) \
			echo "starting the Compose test database"; \
			$(COMPOSE) --profile test up -d --wait db-test ;; \
	esac
	cd backend && uv run ruff check . && uv run mypy src tests && uv run pytest
	$(MAKE) check-api
	@if [ -f frontend/package.json ]; then \
		cd frontend && pnpm typecheck && pnpm lint && pnpm test; \
	else \
		echo "frontend skeleton does not exist yet: skipping the frontend checks"; \
	fi

# Runs the backend tests inside a container, so a machine with only Docker can run them.
test-docker:
	$(COMPOSE) --profile test run --rm test

# Real-browser tests of the screens. They start a separate, throwaway system (compose.e2e.yaml) and remove it afterwards,
# so no development data is touched. Not part of `make test`.
e2e:
	./scripts/e2e.sh

# Regenerate openapi.json (no database needed) and the frontend types, then fail on any difference.
check-api:
	cd backend && uv run python scripts/export_openapi.py
	@if [ -f frontend/package.json ]; then \
		cd frontend && pnpm gen:api; \
	else \
		echo "frontend skeleton does not exist yet: skipping type generation"; \
	fi
	@if git rev-parse --git-dir >/dev/null 2>&1; then \
		if git ls-files --error-unmatch backend/openapi.json >/dev/null 2>&1; then \
			git diff --exit-code -- backend/openapi.json frontend/src/lib/api/generated \
				|| (echo "check-api: the generated files differ from what is committed" && exit 1); \
		else \
			echo "check-api: backend/openapi.json is not committed yet, so there is nothing to compare"; \
		fi; \
	fi

check-spec-first:
	./scripts/check-spec-first.sh
