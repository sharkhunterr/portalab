#!/bin/sh
# Issue 402 — once: make the key pair that signs the published images. The public key goes into the repository
# (portalab/deploy/cosign.pub: commit it); the private key, base64-encoded, and its password go into masked CI
# variables of the GitLab project (COSIGN_KEY_B64, COSIGN_PASSWORD) through glab — then nothing of them stays
# on this machine. Run from the repository root, with glab signed in to the project.
#
#   sh portalab/deploy/ci/setup-signing.sh
set -eu
command -v glab >/dev/null || { echo "glab is needed"; exit 1; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT INT TERM
chmod 700 "$WORK"
PASSWORD="$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | cut -c1-40)"
docker run --rm -u "$(id -u):$(id -g)" -e COSIGN_PASSWORD="$PASSWORD" -v "$WORK:/w" -w /w \
  gcr.io/projectsigstore/cosign:v2.4.1 generate-key-pair >/dev/null
cp "$WORK/cosign.pub" portalab/deploy/cosign.pub
glab variable set COSIGN_KEY_B64 --masked --value "$(base64 -w0 "$WORK/cosign.key")" >/dev/null
glab variable set COSIGN_PASSWORD --masked --value "$PASSWORD" >/dev/null
echo "Signing set up: commit portalab/deploy/cosign.pub; the next release is signed."
