#!/bin/sh
# Issues 395, 400, 402 — what an image must pass before it is published, run on the image itself (the one
# that is then pushed, never a rebuild): it starts; Trivy finds no fixed HIGH or CRITICAL vulnerability; OWASP
# ZAP, signed in, finds nothing its rules fail on; and its SBOM (CycloneDX) is written.
#
#   sh portalab/deploy/ci/check-image.sh IMAGE [OUT_DIR]
set -eu
IMAGE="$1"
OUT="${2:-.}"
HERE="$(cd "$(dirname "$0")" && pwd)"
TRIVY="aquasec/trivy:0.58.1"
mkdir -p "$OUT"

# one image, three entrypoints (serve, worker, migrate): it starts
docker run --rm "$IMAGE" --help >/dev/null

trivy() {
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock "$TRIVY" image --quiet --timeout 20m "$@" "$IMAGE"
}
trivy --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1
trivy --format cyclonedx > "$OUT/sbom.cdx.json"

sh "$HERE/dast.sh" "$IMAGE" "$OUT/dast-report"
