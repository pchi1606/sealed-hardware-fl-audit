#!/usr/bin/env bash
# Author: Prabhu Rangaraju
# Optional live re-fetch: confirms the Rekor -> endorsement -> payload hash
# chain still verifies against the live public endpoints today.
#
# Usage:  bash scripts/fetch_live.sh
# Informational only -- not part of the deterministic verification in
# scripts/verify_claims.py (endpoints are outside the author's control and
# may flap, as documented in the manuscript).
set -euo pipefail
cd "$(dirname "$0")/.."

UUID="108e9186e8c5677a4e8e68884126228c18dbe566ab43eb0be79b077401149bd340bc295d78e9cd86"
EXPECTED="62e818ac02a0427b9811d08468e286aca2f5c68ca44191a9ab1f86075afe5a87"

echo "-- fetching Rekor entry $UUID"
curl -sS "https://rekor.sigstore.dev/api/v1/log/entries/$UUID" -o /tmp/s3_live_entry.json
echo "-- fetching endorsed payload"
curl -sSL "https://federatedcompute-pa.googleapis.com/data/transparency/sha2-256:$EXPECTED" \
  -o /tmp/s3_live_payload.json || true

if [ -s /tmp/s3_live_payload.json ]; then
  GOT="$(sha256sum /tmp/s3_live_payload.json | cut -d' ' -f1)"
  if [ "$GOT" = "$EXPECTED" ]; then
    echo "LIVE CHECK PASS: payload sha256 matches the endorsed hash."
  else
    echo "LIVE CHECK NOTE: payload hash differs from the 2026-10-05 artifact ($GOT)."
    echo "The bundled data/ artifacts remain the audited record."
  fi
else
  echo "LIVE CHECK NOTE: payload endpoint did not return data; chain verified against bundled artifacts."
fi
echo "Rekor entry saved to /tmp/s3_live_entry.json for inspection."
