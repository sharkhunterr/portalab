#!/bin/sh
# Issue 469 — the nightly regression suite: a fresh portal (migrations from scratch, its Admin through the
# arrival wizard, the demo data, every shop product given to the Admin), served with the production bundle,
# then the Playwright matrix of frontend/tests/nightly against it: every interface on a phone, a tablet and
# a desktop, every widget and its options, every statistic locked and unlocked, the shop's products.
#
#   DATABASE_URL=postgresql+asyncpg://… sh tests/nightly/nightly.sh [OUT_DIR] [-- playwright args…]
#   (from portalab/backend, after `npm run build` in portalab/frontend)
set -eu
OUT="$(mkdir -p "${1:-nightly-report}" && cd "${1:-nightly-report}" && pwd)"
[ $# -gt 0 ] && shift
[ "${1:-}" = "--" ] && shift
PORT="${NIGHTLY_PORT:-8098}"
BASE="http://127.0.0.1:${PORT}"
FRONTEND="$(cd ../frontend && pwd)"
SCRATCH="$(mktemp -d)"
export NIGHTLY_MATRIX="$SCRATCH/matrix.json"
umask 077
head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$SCRATCH/secret_key"
export SECRET_KEY_FILE="$SCRATCH/secret_key"
export DATA_DIR="$SCRATCH/data"
mkdir -p "$DATA_DIR"
export SETUP_NETWORKS="127.0.0.0/8"
STATE="$SCRATCH/state.json"

serve() {
  uv run python -m tests.nightly.serve "$PORT" "$FRONTEND/dist" >> "$OUT/server.log" 2>&1 &
  SERVER=$!
}
SERVER=""
trap '[ -n "$SERVER" ] && kill $SERVER 2>/dev/null; rm -rf "$SCRATCH"' EXIT INT TERM

uv run portalab migrate > "$OUT/prepare.log" 2>&1
serve
uv run python -m tests.nightly.prepare admin "$BASE" "$STATE" >> "$OUT/prepare.log" 2>&1
# the demo data (members, shop, packs, news, wiki…) through the modules' services, as `portalab demo seed`
uv run portalab demo seed --users-file "$SCRATCH/demo-users.txt" >> "$OUT/prepare.log" 2>&1 || true
# the packs and the catalog the seed added, as a restarted portal reads them
kill "$SERVER" 2>/dev/null || true
wait "$SERVER" 2>/dev/null || true
serve
uv run python -m tests.nightly.prepare grant "$BASE" "$STATE" >> "$OUT/prepare.log" 2>&1
tail -n 3 "$OUT/prepare.log"

# the matrix in NIGHTLY_SHARDS parts (3 by default), one each night in turn: all of it every NIGHTLY_SHARDS nights,
# about an hour a night on the shared runner; NIGHTLY_SHARDS=1 runs all of it (a weekend, by hand). A run
# given Playwright arguments (a part of the matrix, by hand) is not cut, unless NIGHTLY_SHARDS says so
if [ $# -gt 0 ]; then SHARDS="${NIGHTLY_SHARDS:-1}"; else SHARDS="${NIGHTLY_SHARDS:-3}"; fi
for arg in "$@"; do case "$arg" in --shard*) SHARDS=1 ;; esac; done
PART_ARG=""
if [ "$SHARDS" -gt 1 ]; then
  PART=$(( $(date +%j | sed 's/^0*//') % SHARDS + 1 ))
  PART_ARG="--shard=$PART/$SHARDS"
  echo "tonight: part $PART of $SHARDS of the matrix"
fi

status=0
# (the Playwright arguments given after « -- »: -g "interface vhs", --project=phone…)
(cd "$FRONTEND" && NIGHTLY_STATE="$STATE" NIGHTLY_OUT="$OUT" \
  npx playwright test --config playwright.nightly.config.ts ${PART_ARG:+"$PART_ARG"} "$@") || status=$?
exit $status
