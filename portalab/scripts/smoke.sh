#!/usr/bin/env bash
# Portalab foundation smoke checks — the 8 acceptance checks of specs/001-portal-global-spec/quickstart.md.
# Requirements: docker, uv, node/npm. Run from anywhere:  portalab/scripts/smoke.sh
# Uses throwaway containers/network and test-only credentials; nothing is pushed or kept.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$APP_DIR/.." && pwd)"
BACKEND="$APP_DIR/backend"
FRONTEND="$APP_DIR/frontend"
IMAGE="${PORTALAB_IMAGE:-portalab:smoke}"
NET="portalab-smoke-$$"
PG="portalab-smoke-pg-$$"
APP="portalab-smoke-app-$$"
WORKER="portalab-smoke-worker-$$"
PORT="${SMOKE_PORT:-18080}"
SECRETS="$(mktemp -d)"
DB_PASSWORD="smoke-only-$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
FORBIDDEN_IMPORT="$BACKEND/src/portalab/core/_smoke_forbidden.py"
PASSED=0

cleanup() {
  rm -f "$FORBIDDEN_IMPORT"
  docker rm -f -v "$APP" "$WORKER" "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -rf "$SECRETS"
}
trap cleanup EXIT

ok() { PASSED=$((PASSED + 1)); printf '  \033[32m✔\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$1"; exit 1; }
wait_http() { # url expected_status timeout
  for _ in $(seq 1 "$3"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' "$1" || true)" = "$2" ] && return 0
    sleep 1
  done
  return 1
}

echo "▶ building image $IMAGE"
docker build -q -f "$APP_DIR/deploy/Dockerfile" -t "$IMAGE" "$REPO_DIR" >/dev/null

echo "▶ starting PostgreSQL"
docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" -e POSTGRES_DB=portalab -e POSTGRES_USER=portalab \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" postgres:16-alpine >/dev/null
for _ in $(seq 1 30); do docker exec "$PG" pg_isready -U portalab -q && break; sleep 1; done
echo "postgresql://portalab:$DB_PASSWORD@$PG:5432/portalab" > "$SECRETS/database_url"
head -c 48 /dev/urandom | base64 > "$SECRETS/secret_key"
chmod 755 "$SECRETS"; chmod 644 "$SECRETS"/*  # readable by the non-root container user (uid 10001)
RUN_ARGS=(--network "$NET" -v "$SECRETS:/run/secrets:ro" -e DATABASE_URL_FILE=/run/secrets/database_url
  -e SECRET_KEY_FILE=/run/secrets/secret_key)

echo "▶ checks"
# 1. health / readiness before and after migration
docker run -d --name "$APP" "${RUN_ARGS[@]}" -p "127.0.0.1:$PORT:8080" "$IMAGE" serve >/dev/null
wait_http "http://127.0.0.1:$PORT/healthz" 200 30 || fail "1. /healthz did not answer 200"
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/readyz")" = "503" ] \
  || fail "1. /readyz must be 503 before migrations"
docker run --rm "${RUN_ARGS[@]}" "$IMAGE" migrate >/dev/null
wait_http "http://127.0.0.1:$PORT/readyz" 200 15 || fail "1. /readyz did not flip to 200 after migrate"
ok "1. /healthz 200; /readyz 503 → 200 only after migrations"

# 2. boundary lint fails on a forbidden import
(cd "$BACKEND" && uv run lint-imports --config importlinter.ini >/dev/null) || fail "2. boundaries broken before probe"
echo "import portalab.app.main  # noqa: F401 — smoke probe" > "$FORBIDDEN_IMPORT"
if (cd "$BACKEND" && uv run lint-imports --config importlinter.ini >/dev/null 2>&1); then
  fail "2. a forbidden import (core → app) was not detected"
fi
rm -f "$FORBIDDEN_IMPORT"
ok "2. import-linter passes and rejects a forbidden import"

# 3 & 4. migration tests and job semantics (real PostgreSQL)
TEST_URL="postgresql://portalab:$DB_PASSWORD@127.0.0.1:55433/postgres"
docker rm -f -v "$PG-tests" >/dev/null 2>&1 || true
docker run -d --name "$PG-tests" -e POSTGRES_USER=portalab -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -e POSTGRES_DB=postgres -p 127.0.0.1:55433:5432 postgres:16-alpine >/dev/null
trap 'docker rm -f -v "$PG-tests" >/dev/null 2>&1 || true; cleanup' EXIT
for _ in $(seq 1 30); do docker exec "$PG-tests" pg_isready -U portalab -q && break; sleep 1; done
sleep 1
(cd "$BACKEND" && PORTALAB_TEST_DATABASE_URL="$TEST_URL" PORTALAB_REQUIRE_DB=1 uv run pytest -q \
  tests/integration/test_migrations.py tests/integration/test_migration_upgrade.py >/dev/null) \
  || fail "3. migration tests failed"
ok "3. migrations upgrade an empty DB and the previous release (with data)"
(cd "$BACKEND" && PORTALAB_TEST_DATABASE_URL="$TEST_URL" PORTALAB_REQUIRE_DB=1 uv run pytest -q \
  tests/integration/test_jobs_dedup.py tests/integration/test_jobs_claim.py >/dev/null) \
  || fail "4. job tests failed"
ok "4. same dedup_key runs once; a crashed worker's job is re-claimed"

# 5. default-deny
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/v1/stream")" = "401" ] \
  || fail "5. unauthenticated /api/v1/stream must be 401"
ok "5. unauthenticated access to a protected route is refused"

# 6. logs: correlation id present, no secret
curl -s -o /dev/null -H "X-Correlation-Id: smoke-corr-42" "http://127.0.0.1:$PORT/healthz"
sleep 1
LOGS="$(docker logs "$APP" 2>&1)"
echo "$LOGS" | grep -q '"correlation_id": "smoke-corr-42"' || fail "6. correlation id missing from logs"
if echo "$LOGS" | grep -qF "$DB_PASSWORD"; then fail "6. a secret leaked into the logs"; fi
ok "6. logs carry the correlation id and no secret value"

# 7. API contract drift (backend snapshot + generated client)
(cd "$BACKEND" && uv run pytest -q tests/contract/test_openapi_snapshot.py >/dev/null) || fail "7. OpenAPI snapshot drift"
(cd "$FRONTEND" && node scripts/check-api-drift.mjs >/dev/null) || fail "7. generated client drift"
ok "7. OpenAPI schema and generated client match"

# 8. one image, two roles
docker run -d --name "$WORKER" "${RUN_ARGS[@]}" "$IMAGE" worker >/dev/null
started=""
for _ in $(seq 1 30); do
  if docker logs "$WORKER" 2>&1 | grep -q '"message": "worker started"'; then started=1; break; fi
  [ "$(docker inspect -f '{{.State.Running}}' "$WORKER")" = "true" ] || break
  sleep 1
done
if [ -z "$started" ]; then
  docker logs "$WORKER" 2>&1 | tail -20 >&2
  fail "8. worker did not start"
fi
ok "8. the same image runs as serve and as worker"

echo "✔ all $PASSED smoke checks passed"
