# Reproduction package — "Verifiability Is a Spectrum: An Outsider's Audit of Google's Sealed-Hardware Federated Learning Pipeline"

One-command offline verification of the manuscript's headline numbers from the
bundled raw artifacts.

**Author:** Prabhu Rangaraju

## One command

```bash
bash reproduce.sh
```

Requires Python 3.10+ only (standard library; no third-party packages).

## What it does

`scripts/verify_claims.py` recomputes every headline claim from the raw
artifacts in `data/` and checks each against `expected/expected.json`,
printing PASS/FAIL per check:

- SHA-256 of the endorsement statement equals the Rekor-endorsed hash
  (`62e818ac…`); the statement's subject digest equals the KMS binary
  digest (`d14a1852…`)
- Rekor entry identity: UUID, log index 1634041292, integrated time
  2026-05-26T16:54:44Z
- All 20 SLSA attestation bundles decode (stdlib DSSE parse): 20 distinct
  git commits, one builder id, one build type, every subject digest equal
  to the KMS digest
- 9 endorsement keys in `gboard.txtpb`: SHA-256 fingerprints recomputed
  from the DER blobs; first fingerprint `3ebd2cd4…`
- Endorsement validity window: 45 days (2026-05-26 → 2026-07-10); the
  90-day freshness acceptance window is a separate parameter
- Log-scale and enumeration arithmetic: ≈10.6M entries/day (≈123/s);
  90-day window ≈958M entries ≈22 days at 500 entries/s, ≈5.5 days at
  2000/s, ≈3.5 TB at 3.6 KB/entry
- Build recipe fields (machine type, `--lockfile_mode=error`,
  `retention-days: 5`) and the documented build-attempt failure
  (`NoSuchElementException` / `doTunneling` / `EXIT=37`)
- Key-indexed log-search failure record and hash-index search artifact

Expected runtime: under a minute on a modest laptop.

## Data

`data/` bundles public records fetched 2026-10-04/05 from public endpoints
(`rekor.sigstore.dev`, `federatedcompute-pa.googleapis.com`,
`api.github.com`) plus `gboard.txtpb` from the Apache-2.0-licensed
`google-parfait/confidential-federated-compute` repository (license header
retained in the file). No credentials, devices, or private data were used.
`scripts/fetch_live.sh` optionally re-fetches the live endpoints to confirm
the hash chain still verifies today (informational; endpoints may flap).

## Citation

See `CITATION.md`.
