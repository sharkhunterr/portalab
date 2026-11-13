#!/bin/sh
# Issue 401 — fuzz the API from its OpenAPI contract: the portal (tests/fuzz/serve.py) on a fresh database,
# an Admin made through the arrival wizard, then Schemathesis signed in as that Admin. No answer may be a
# server error (5xx). Routes that would end the session or wipe the portal mid-run are left out
# (deploy/ci/schemathesis-exclude.txt).
#
#   DATABASE_URL=postgresql+asyncpg://… sh tests/fuzz/fuzz.sh [OUT_DIR]   (from portalab/backend)
set -eu
OUT="${1:-fuzz-report}"
PORT="${FUZZ_PORT:-8099}"
BASE="http://127.0.0.1:${PORT}"
mkdir -p "$OUT"
SCRATCH="$(mktemp -d)"
umask 077
head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$SCRATCH/secret_key"
export SECRET_KEY_FILE="$SCRATCH/secret_key"
export DATA_DIR="${DATA_DIR:-$SCRATCH/data}"
mkdir -p "$DATA_DIR"
export SETUP_NETWORKS="127.0.0.0/8"

uv run portalab migrate >/dev/null
uv run python -m tests.fuzz.serve "$PORT" > "$OUT/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true; rm -rf "$SCRATCH"' EXIT INT TERM
eval "$(uv run python -m tests.fuzz.sign_in "$BASE")"
[ -n "$TOKEN" ] && [ -n "$CSRF" ] || { echo "could not sign in"; exit 1; }

status=0
uvx --quiet "schemathesis==4.33.4" --config-file tests/fuzz/schemathesis.toml run openapi.json --url "$BASE" \
  -H "Cookie: portalab_session=${TOKEN}; portalab_csrf=${CSRF}" -H "X-CSRF-Token: ${CSRF}" \
  --checks not_a_server_error --max-examples "${MAX_EXAMPLES:-15}" --workers "${WORKERS:-2}" \
  --request-timeout 30 --exclude-path-regex "$(cat ../deploy/ci/schemathesis-exclude.txt)" \
  ${INCLUDE:+--include-path-regex "$INCLUDE"} \
  --report junit --report-dir "$OUT" || status=$?
# whether the session survived the run (a route that ends it would hide every route after it)
uv run python - "$BASE" "$TOKEN" > "$OUT/session-after.txt" 2>&1 <<'PY' || true
import sys, urllib.request, urllib.error
request = urllib.request.Request(sys.argv[1] + "/api/v1/me", headers={"Cookie": "portalab_session=" + sys.argv[2]})
try:
    print(urllib.request.urlopen(request, timeout=10).status)
except urllib.error.HTTPError as error:
    print(error.code, error.read()[:300])
PY
exit $status
