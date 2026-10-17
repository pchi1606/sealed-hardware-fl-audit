# data/ — bundled raw artifacts

Author: Prabhu Rangaraju

Each file below is a raw, unmodified artifact from the audit. The verifier
(`../scripts/verify_claims.py`) recomputes the manuscript's headline numbers
from these files.

| File | What it is |
|---|---|
| `rekor_kms_example.json` | Rekor transparency-log entry for the KMS endorsement (fetched 2026-10-05 from `rekor.sigstore.dev`) |
| `endorsement_kms_example.json` | Endorsed Oak/in-toto statement payload (fetched 2026-10-05 from `federatedcompute-pa.googleapis.com`) |
| `gh_attestation_kms.json` | 20 SLSA v1 attestation bundles from the GitHub Attestation API (fetched 2026-10-05) |
| `commit_dates_20261008.json` | Committer dates for the 20 attestation commits, via `api.github.com` (fetched 2026-10-08) |
| `gboard.txtpb` | Gboard access-policy reference values: 8 endorsement keys + 1 Rekor log-verification key (Apache-2.0, from `google-parfait/confidential-federated-compute`; license header retained) |
| `endorsement_gboard_policy.json` | Gboard policy endorsement reference (fetched 2026-10-05) |
| `rekor_pubkey.pem` | Rekor public key used for entry verification |
| `hashsearch_kms.json` | UUID list from the Rekor hash-index search (2026-10-05) |
| `keysearch_bg_result.json` / `keysearch_bg.log` | Key-indexed log-search attempt: `RemoteDisconnected` timeout (2026-10-05) |
| `prov_uuid_entry.json` | Provenance UUID entry record (2026-10-05) |
| `uuid_kind_scan.txt` | Entry-kind scan notes (2026-10-05) |
| `reusable_build.yaml` | GitHub Actions reusable build recipe (from `google-parfait/confidential-federated-compute`) |
| `build_kms_attempt.log` | Bazel rebuild attempt, 2026-10-05 (`NoSuchElementException` / `doTunneling` / `EXIT=37`) |
| `build_reattempt_20261006.log` | Bazel rebuild re-attempt, 2026-10-06 (identical failure) |
| `treesize_20261008.json` | Rekor tree-size measurement transcript, 2026-10-08 (method: `../scripts/measure_tree_size.py`; note the endpoint flapping documented in the manuscript) |
| `endpoint_probe_20261008.txt` | Live endpoint status transcript, 2026-10-08 (`log/info` → HTTP 404) |

No credentials, devices, or private data were used to produce any file here.
