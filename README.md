# Reproduction package — "Verifiability Is a Spectrum: An Outsider's Audit of Google's Sealed-Hardware Federated Learning Pipeline"

One-command offline verification of the manuscript's headline numbers from the
bundled raw artifacts.

## One command

```bash
bash reproduce.sh
```

Requires Python 3.10+ only (standard library; no third-party packages).

## What it does

`scripts/verify_claims.py` recomputes every headline claim from the raw
artifacts in `data/` and checks each against `expected/expected.json`,
printing PASS/FAIL per check. `scripts/envelope_enumerator.py`
recomputes the manuscript's §5 variant family and joint envelope from
`AUDIT_MATRIX.md`, including the wider named-alternative stacks the
printed envelope excludes by its stated strict-direction axis:

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
  90-day window ≈958M entries. At the **measured** naive-path retrieval
  rate (≈9.7 entries/s, 2026-11-04 experiment) scanning that window
  would take ≈1,142 days (≈3 years) — the naive path's cost, not the
  enumeration route's. The audit's original October estimate
  (≈22 days at a stipulated 500 entries/s, ≈5.5 days at 2000/s,
  ≈3.5 TB at 3.6 KB/entry) is retained in the verifier only as a
  labelled SUPERSEDED check; the manuscript marks it superseded and
  it should not be cited.
- All-keys census (2026-11-04): per-key entry counts from
  `data/census_2026-11-04.json` sum to the recorded total of 509,569
  entries over 19 published endorsement keys; the exemplar key's
  census count is 115.
- Build recipe fields (machine type, `--lockfile_mode=error`,
  `retention-days: 5`) and the documented build-attempt failure
  (`NoSuchElementException` / `doTunneling` / `EXIT=37`)
- The October first pass's key-search record (a wrong-endpoint attempt,
  retained as method history) and the hash-index search artifact

Expected runtime: under a minute on a modest laptop.

## Data

`data/` bundles public records fetched 2026-10-04/05 and 2026-11-04 from public endpoints
(`rekor.sigstore.dev`, `federatedcompute-pa.googleapis.com`,
`api.github.com`) plus `gboard.txtpb` from the Apache-2.0-licensed
`google-parfait/confidential-federated-compute` repository (license header
retained in the file). No credentials, devices, or private data were used.
`scripts/fetch_live.sh` optionally re-fetches the live endpoints to confirm
the hash chain still verifies today (informational; endpoints may flap).

## Citation

See `CITATION.md`.

## Provenance and split hygiene (r6 note)

This is an audit package, not a modeling package: there are no
datasets and no train/test split. The bundled data are public audit
artifacts (transparency-log and API responses plus one configuration
file), fetched from the public endpoints named in the Data section
above, each under its source's public terms (the configuration file
comes from an Apache-2.0-licensed repository, as noted there).
Nothing was fit, trained, or tuned on the bundled records; they are
evidence, reproduced so any reader can re-derive the audit's claims.

## Package contents and integrity

- `AUDIT_MATRIX.md` — the full 27-row audit matrix (claim, score,
  evidence/procedure per row).
- `PILOT_REPORT.md` — the pilot report for the October audit window.
- `AMENDMENT-2026-11-04.md` — the experiment amendment frozen before
  any of its 2026-11-04 runs (E1–E8 series).
- `records/` — the 2026-11-04 experiment and scoring records: the
  all-keys census and signature authentication (E8), the documented
  build (E6), the wire-format policy-artifact decode and the
  client-code inspection (E10/E11, with the decoded workload
  programs in `data/`), the second-scorer exercise, and the blind
  artifact-level re-scoring of the final matrix (scoring sheet +
  adjudications).
- `SHA256SUMS` — SHA-256 of every file in this package **except**
  `paper.pdf` and `SHA256SUMS` itself. The bundled manuscript copy is
  excluded because the manuscript states the manifest's own SHA-256;
  every other file — including this README — is covered, so any reader
  can verify the package's contents against the hash printed in the
  paper. Verify with `sha256sum -c SHA256SUMS`.
