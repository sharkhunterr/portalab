#!/bin/sh
# Issue 400 — OWASP ZAP against a running portal: a throwaway database and portal from IMAGE (hardened as in
# the Compose file), an Admin made through the arrival wizard, then ZAP's baseline (spider + passive rules)
# signed in as that Admin. A rule set to FAIL in zap-rules.conf fails the job; a WARN is reported. Only Docker
# is needed; files go in and out with « docker cp » and a volume (works on Docker-in-Docker).
#
#   sh portalab/deploy/ci/dast.sh IMAGE [OUT_DIR]
set -eu

IMAGE="$1"
OUT="${2:-dast-report}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ID="dast-$$"
ZAP_IMAGE="ghcr.io/zaproxy/zaproxy@sha256:030d3df57735dacbb83464854758e674dd9ad01d79d12a129a8e58b1fd384238"  # stable, pinned
PY_IMAGE="python:3.12-slim"
mkdir -p "$OUT"

secret() { head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
DB_PASSWORD="$(secret)"

cleanup() {
  docker rm -f "$ID-app" "$ID-db" "$ID-zap" "$ID-in" >/dev/null 2>&1 || true
  docker volume rm "$ID-secrets" >/dev/null 2>&1 || true
  docker network rm "$ID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker network create "$ID" >/dev/null
docker run -d --name "$ID-db" --network "$ID" -e POSTGRES_DB=portalab -e POSTGRES_USER=portalab \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" postgres:16-alpine >/dev/null
until docker exec "$ID-db" pg_isready -h 127.0.0.1 -U portalab -d portalab >/dev/null 2>&1; do sleep 1; done

# the secrets as files, in a volume the portal mounts read-only (as the Compose file does)
docker volume create "$ID-secrets" >/dev/null
docker run --rm -v "$ID-secrets:/s" -e KEY="$(secret)" \
  -e URL="postgresql+asyncpg://portalab:${DB_PASSWORD}@${ID}-db:5432/portalab" alpine:3.20 \
  sh -c 'printf %s "$KEY" > /s/secret_key && printf %s "$URL" > /s/database_url && chown 10001 /s/* && chmod 400 /s/*'
run() {  # run COMMAND [docker options…]
  command="$1"
  shift
  docker run "$@" --network "$ID" -v "$ID-secrets:/run/secrets:ro" \
    -e DATABASE_URL_FILE=/run/secrets/database_url -e SECRET_KEY_FILE=/run/secrets/secret_key \
    --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true "$IMAGE" "$command"
}
run migrate --rm
run serve -d --name "$ID-app" >/dev/null
BASE="http://${ID}-app:8080"

# the Admin (from the private network the portal trusts for its set-up), signed in
SIGNED="$(docker run --rm --network "$ID" -v "$HERE/../../backend/tests/fuzz:/f:ro" "$PY_IMAGE" \
  python /f/sign_in.py "$BASE" 2>/dev/null || true)"
if [ -z "$SIGNED" ]; then  # Docker-in-Docker cannot mount the job's files: the helper goes in by copy
  docker create --name "$ID-in" --network "$ID" "$PY_IMAGE" python /tmp/sign_in.py "$BASE" >/dev/null
  docker cp "$HERE/../../backend/tests/fuzz/sign_in.py" "$ID-in:/tmp/sign_in.py"
  SIGNED="$(docker start -a "$ID-in")"
fi
TOKEN="$(printf '%s\n' "$SIGNED" | sed -n 's/^TOKEN=//p')"
CSRF="$(printf '%s\n' "$SIGNED" | sed -n 's/^CSRF=//p')"
[ -n "$TOKEN" ] && [ -n "$CSRF" ] || { echo "could not sign in"; exit 1; }

status=0
# ZAP reads its rules from, and writes its reports to, /zap/wrk (made here: no folder is mounted)
docker create --name "$ID-zap" --network "$ID" -e BASE="$BASE" \
  -e REPLACE="portalab_session=${TOKEN};portalab_csrf=${CSRF}" "$ZAP_IMAGE" sh -c '
mkdir -p /zap/wrk && cp /tmp/rules.conf /zap/wrk/rules.conf && cd /zap/wrk &&
zap-baseline.py -t "$BASE" -m 3 -c rules.conf -J zap.json -r zap.html -z "
-config replacer.full_list(0).description=session -config replacer.full_list(0).enabled=true
-config replacer.full_list(0).matchtype=REQ_HEADER -config replacer.full_list(0).matchstr=Cookie
-config replacer.full_list(0).regex=false -config replacer.full_list(0).replacement=$REPLACE"' >/dev/null
docker cp "$HERE/zap-rules.conf" "$ID-zap:/tmp/rules.conf"
docker start -a "$ID-zap" || status=$?
docker cp "$ID-zap:/zap/wrk/zap.json" "$OUT/zap.json" 2>/dev/null || true
docker cp "$ID-zap:/zap/wrk/zap.html" "$OUT/zap.html" 2>/dev/null || true
[ "$status" -eq 2 ] && status=0  # 2: warnings only
exit "$status"
