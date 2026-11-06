# S3 Pilot Report — 2026-10-04/05

**Verdict: GO.** The audit is empirically grounded. Public artifacts were pulled and
verification was *attempted and partially completed* with real hashes, not just
documented. One discovery path is degraded (documented below as a finding, not a blocker).

## What was pulled and verified (all real, recomputed)

1. **Paper + blog**: arXiv:2609.31494 v4 (2026-09-30) full text; Google Research blog
   (2026-10-02). Title changed v1 "verifiably" → v4 "provably" — noted for the manuscript.

2. **Source repo**: `github.com/google-parfait/confidential-federated-compute` cloned
   (also `google-parfait/federated-compute` for the `access_policy.proto`).
   Audit methodology docs: `docs/inspecting_endorsements.md` (899 lines),
   `docs/inspecting_attestation_records.md`, `docs/README.md`.

3. **Endorsement keys**: `access_policy_reference_values/gboard.txtpb` parsed —
   9 unique ECDSA-P256 endorsement keys for Gboard (vs 1 in the Feb-2025 docs example:
   key rotation/expansion is itself observable). Fingerprints recomputed from raw DER —
   all match the comments in the file.

4. **Rekor chain (end-to-end, hash-verified)**:
   - Rekor entry `108e9186e8c5677a4e8e68884126228c18dbe566ab43eb0be79b077401149bd340bc295d78e9cd86`
     (logIndex 1634041292, integratedTime 1779814484 = 2026-05-26T16:54:44Z) fetched via
     `rekor.sigstore.dev/api/v1/log/entries/{uuid}`.
   - Endorsed hash `62e818ac02a0427b9811d08468e286aca2f5c68ca44191a9ab1f86075afe5a87`
     extracted from the entry body; endorsement statement fetched from
     `federatedcompute-pa.googleapis.com/data/transparency/sha2-256:{hash}`;
     **SHA-256 of fetched bytes == endorsed hash (match verified in code)**.
   - Endorsement subject: KMS binary digest
     `d14a1852f08b528f9975245f300d44e2500aaff9c8a9c5572e0114b7203e3e47`,
     validity 2026-05-26 → 2026-07-10 (90 days).
   - GitHub API: Actions run 26261649715 ("Build and attest", completed/success,
     head_sha `fe439180bb24e65ad46e869eddee88f9c9b34875`) — exactly the commit the
     docs claim built that binary. Workflow `.github/workflows/build.yaml` + 28 jobs
     (incl. `kms`, `program_containers`) all public.

5. **Reproducibility evidence (the empirical core)**:
   - Hash-index search (`POST /api/v1/index/retrieve {"hash":"sha256:d14a1852…"}`)
     returned **20 Rekor UUIDs**, all DSSE/GitHub-attestation entries referencing the
     same KMS binary digest, logIndexes spanning 1596946374 (≈Feb 2026) → 1712276265.
   - GitHub Attestation API (`/attestations/sha256:d14a1852…`): **20 SLSA v1 provenance
     statements, 20 distinct source commits, all with subject digest == d14a1852…**,
     builder `…/reusable_build.yaml`, buildType `actions.github.io/buildtypes/workflow/v1`.
     I.e., 20 independent CI builds from 20 different commits produced the byte-identical
     binary — the reproducibility claim holds up observationally.
   - **Direct rebuild ATTEMPTED**: `bazelisk build -c opt //kms:main` (Bazel 8.2.1).
     Failed at dependency-download stage: Bazel's Java HTTP client throws
     `NoSuchElementException` in `doTunneling` against this environment's authenticated
     egress proxy (EXIT=37), before any compilation. Full build additionally infeasible
     here (2 vCPU / 7 GB RAM / ~5 GB disk vs. Oak-monorepo dependency closure).
     Recorded as ATTEMPTED/ENV-BLOCKED, not as a negative result about Google's claim.
     Log: `logs/build_kms_attempt.log`.

6. **Rekor log scale (measured)**: binary search on `logIndexes` retrieve →
   current max index ≈ **3,028,925,672** (2026-10-04). Growth since 2026-05-26:
   1,394,884,380 entries / 131 days ≈ **10.6M entries/day (~123/sec)**.

## Gaps / findings (these shape the paper, not kill it)

- **F1 — Public-key → entries search is degraded.** `POST /api/v1/log/entries/retrieve
  {"publicKey":…}` times out (>60s, also >540s background); `search.sigstore.dev`
  operators API (`/api/v1/search`) drops connections. The search UI's own JS confirms
  the current index only supports email/hash/commitSha/uuid/logIndex — **no public-key
  search**. The docs' recommended discovery path (rekor-monitor / BigQuery) is
  effectively: full-log scan (infeasible at 10.6M/day) or BigQuery (needs GCP auth).
  → *Finding*: an outsider today cannot enumerate "the complete set of workloads"
  from the log without privileged search access. The paper's §4.2 claim ("third-party
  auditors can also know the full set…") is therefore **conditionally checkable** —
  true in principle, degraded in current infrastructure.
- **F2 — Current Gboard policy bytes not yet obtained** (blocked by F1). Worked audit
  will use (a) the live KMS/binary chain above, (b) the paper's Listing-2 policy as the
  worked program-analysis example (labeled as such), (c) forward monitoring via the
  Pub/Sub event stream for new endorsements.
- **F3 — Transparency-store retention**: the docs' Feb-2025 Gboard endorsement
  (`d72534e0…`) and policy (`a324fe96…`) now return Bad Request — consistent with the
  documented ≥1-year retention. Historical-policy archaeology is time-bounded;
  **continuous monitoring is required** to keep C7 checkable. Also: endorsement
  validity is 90 days; reference values pin `not_before_absolute=2025-02-15` and
  90-day relative window.
- **F4 — Rekor v1 API partially deprecated**: `log/info` → 404; `entries/retrieve`
  by `entryUUIDs` → connection drop; by `logIndexes` → works. Methodology must pin
  exact working endpoints.

## Go criterion check

"Can actually pull public artifacts and attempt verification" — **yes**: Rekor entries,
endorsement statements, SLSA provenance, build workflows, endorsement keys, source —
all pulled; hash-chain verification recomputed in code; reproducible-build attempted
with documented outcome. Claims are operationalizable (checklist in CLAIM_INVENTORY.md).
**Proceed to Phase 2.**
