#!/bin/sh
# Issue 402 — sign the published image by its digest with cosign, attach its SBOM as a signed attestation, and
# check both with the public key kept in the repository (portalab/deploy/cosign.pub). The private key comes
# base64-encoded in COSIGN_KEY_B64 with its password in COSIGN_PASSWORD (masked CI variables); registry
# credentials in REGISTRY_USER / REGISTRY_TOKEN. Files go in with « docker cp » (Docker-in-Docker).
#
#   sh portalab/deploy/ci/sign-image.sh REPOSITORY@sha256:DIGEST [SBOM]
set -eu
REF="$1"
SBOM="${2:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
COSIGN="gcr.io/projectsigstore/cosign:v2.4.1"
ID="cosign-$$"
case "$REF" in *@sha256:*) ;; *) echo "sign a digest (repository@sha256:…), never a tag"; exit 1 ;; esac

cleanup() { docker rm -f "$ID" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

cosign() {  # cosign ARGS… — the key, the public key and the SBOM copied in first
  # as root: « docker cp » keeps the key's owner and mode (root, 0600), which cosign's nonroot user cannot read
  docker create --name "$ID" --user 0:0 -e COSIGN_PASSWORD -e COSIGN_YES=true "$COSIGN" "$@" >/dev/null
  (umask 077 && printf '%s' "$COSIGN_KEY_B64" | base64 -d > /tmp/cosign.key.$$)
  docker cp /tmp/cosign.key.$$ "$ID:/tmp/cosign.key" && rm -f /tmp/cosign.key.$$
  docker cp "$HERE/../cosign.pub" "$ID:/tmp/cosign.pub"
  [ -n "$SBOM" ] && docker cp "$SBOM" "$ID:/tmp/sbom.cdx.json"
  docker start -a "$ID"
  docker rm -f "$ID" >/dev/null
}
AUTH="--registry-username=$REGISTRY_USER --registry-password=$REGISTRY_TOKEN"

# shellcheck disable=SC2086
cosign sign --key /tmp/cosign.key $AUTH "$REF"
if [ -n "$SBOM" ]; then
  # shellcheck disable=SC2086
  cosign attest --key /tmp/cosign.key --type cyclonedx --predicate /tmp/sbom.cdx.json $AUTH "$REF"
fi
# shellcheck disable=SC2086
cosign verify --key /tmp/cosign.pub $AUTH "$REF" >/dev/null
echo "signed and verified: $REF"
