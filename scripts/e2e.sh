#!/usr/bin/env bash
# Browser tests: start a throwaway system (compose.e2e.yaml), run the Playwright tests against it,
# and always remove it afterwards. Needs Docker and a Chrome installed on this machine
# (set E2E_BROWSER_CHANNEL=chromium after `pnpm exec playwright install chromium` to use Playwright's own).
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PROJECT=docs-studio-e2e
# An absolute path: the clean-up below runs after the script has moved into frontend/.
COMPOSE=(docker compose -p "$PROJECT" -f "$ROOT/compose.e2e.yaml")

cleanup() { "${COMPOSE[@]}" down -v || true; }
trap cleanup EXIT

if [ ! -f .env ]; then
  echo "e2e: copy .env.example to .env first (the database password comes from it)" >&2
  exit 2
fi
set -a; . ./.env; set +a

echo "e2e: starting the throwaway system"
"${COMPOSE[@]}" up -d --build

for _ in $(seq 1 90); do
  if curl -fsS -o /dev/null http://localhost:18000/healthz && curl -fsS -o /dev/null http://localhost:13000/docs; then
    ready=1; break
  fi
  sleep 2
done
if [ -z "${ready:-}" ]; then
  echo "e2e: the system did not become ready" >&2
  "${COMPOSE[@]}" logs --tail=40 >&2 || true
  exit 1
fi

echo "e2e: running the browser tests"
cd frontend
E2E_BASE_URL=http://localhost:13000 E2E_API_URL=http://localhost:18000 pnpm e2e "$@"
