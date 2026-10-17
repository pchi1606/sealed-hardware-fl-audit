#!/usr/bin/env bash
# Author: Prabhu Rangaraju
# One-command reproduction of the S3 sealed-hardware audit headline numbers.
#
# Usage:  bash reproduce.sh
# Run from this directory. Requires Python 3.10+ only (stdlib, no pip needed).
#
# What it does:
#   1. recomputes every headline claim of the manuscript from the bundled
#      raw artifacts in data/ (Rekor entry, endorsement statement, SLSA
#      attestation bundles, endorsement keys, build recipe and logs)
#   2. verifies each recomputed value against expected/expected.json and
#      reports PASS/FAIL per check
#
# The bundled data/ artifacts are public records fetched 2026-10-04/05 from
# public endpoints (rekor.sigstore.dev, federatedcompute-pa.googleapis.com,
# api.github.com) plus Apache-2.0 repository files. No network access is
# needed. scripts/fetch_live.sh optionally re-fetches the live endpoints to
# confirm the hash chain still verifies today.
#
# Expected runtime: under a minute on a modest laptop.
set -euo pipefail
cd "$(dirname "$0")"

echo "================================================================"
echo " Verifying S3 headline claims against bundled artifacts"
echo "================================================================"
python3 scripts/verify_claims.py
