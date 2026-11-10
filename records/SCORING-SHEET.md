# Blind artifact-level re-scoring — S3 final claim matrix (build 04094abd)

**Exercise:** ledger item F8 (the NEW-WORK reliability item from the Perplexity
fix round). **Date:** 2026-11-04. **Scorer:** blind re-scoring agent, working
from artifact-level evidence only.

## Method

Each of the 27 full-matrix rows was scored from the evidence record — the
sealed artifact and reproduction packages, the E1–E8 experiment records
(E-results.md, E6-results.md, perplexity-fixround/E8-census-signatures.md,
perplexity-fixround/ADJUDICATIONS.md), the retained raw logs, and the local
repo copies — under the paper's own §3 rubric:

- **V** — the check was executed end-to-end on public artifacts.
- **P** — checkable in principle; degraded or blocked in current infrastructure.
- **T** — no outsider procedure exists; the claim rests on a named trusted party.
- **Rule 1 (disclosure):** a row scores V on a vendor statement only when the
  claim audited *is* the disclosure; where the claim is a fact and the only
  support is the vendor's statement of it, the row scores T.
- **Rule 2 (checkability, not truth):** where an executed check contradicted
  the claim as worded, the score is P read as a negative finding, with the
  contradiction in the basis.
- **Rule 3 (unexecuted procedure):** a row whose procedure exists but was not
  executed scores P, flagged "unexecuted" — never V, never T.

Corroborating precedents applied (all from the published record itself):
claim-as-worded scope (a single executed instance does not lift a
universal-scope claim to V — the B2 precedent); enforcement-inside-TEEs
scores T (the C4b / D3 precedent); claim wording taken from the published
matrix (manuscript Table 5 / AUDIT_MATRIX.md claim column).

Independent spot executions by this scorer (not taken on trust from the
records): `reproduction-package-anon/scripts/verify_claims.py` re-run
offline against the bundled artifacts — **31/31 PASS** (endorsement hash,
subject digest, Rekor entry identity, 20-attestation set, key fingerprints,
45-day validity, 90-day window, census total 509,569); `gboard.txtpb`
lines 87–90 confirm `not_before_absolute` 2025-02-15 and the relative
freshness window at artifact level.

## Scores

| Row | Claim (short) | Blind score | Evidence pointer (one line) |
|---|---|---|---|
| A1 | KMS TEE software recorded in public transparency log (exemplar) | **V** | Entry→payload SHA-256 recomputed (verifier checks 1–3, re-run); RFC 6962 proof folds at leaf index 1512137030 (ADJUDICATIONS (b)); checkpoint sig + SET + endorsement sig all verified (E8 Exp B). |
| A2 | Devices validate KMS key + access policy via endorsements + inclusion proofs | **P** | Client-code static-inspection procedure exists in the public federated-compute client lib but was not executed; device handshake itself unobservable → rule 3, flagged unexecuted. |
| A3 | KMS releases decryption keys only to TEEs matching policy reference values | **T** | Runtime enforcement inside KMS TEEs; no outsider procedure verifies a universal negative about key releases; §5 groups it with the code-inspectable-but-unobservable runtime residual (C4b/D3 enforcement precedent). |
| A4 | Root→worker Noise channel with attestation check | **T** | Internal enclave channel (system paper §3.3.1); no public artifact and no outsider observation point; same runtime-residual class as A3. |
| B1 | KMS + data-processing binaries' source public, with public build recipe | **V** | Repo cloned and inspected (AUDIT.md artifact inventory); recipe fields verified from bundled `reusable_build.yaml` (verifier check 9: runner class, lockfile mode, retention). |
| B2 | Binaries reproducibly buildable (bit-identical) | **P** | One instance executed bit-identical (E6 attempt 3: documented invocation, exit 0, container.tar SHA-256 == endorsed digest d14a1852…); claim as worded covers all binaries — the rest are unexecuted → single-instance scoping. |
| B3 | SLSA provenance for every endorsed binary on Rekor | **P** | Exemplar digest executed: 20 DSSE bundles parsed, one subject digest / one builder (verifier checks 4, 12); every-binary scope unexecuted and the statements' DSSE signatures not independently verified. |
| B4 | Workload Python programs inspectable (embedded in policy) | **P** | Executed retrieval contradicts the claim as worded for the live system: 428 payloads + 21 artifacts scanned, zero embedded programs, zero `_MAX_ZCDP` (E8 Exp A); mechanism documented only (Listing 2) → P as negative finding per rule 2 (the paper's own named case). |
| B5 | Sideloaded proprietary logic stays private | **T** | Fact-claim whose only support is the vendor's characterization; no outsider test distinguishes privacy-relevant from proprietary sideloading → rule 1. |
| C1 | Policy pins exact program + root/worker binary digests at 4 stack layers | **P** | Mechanism in `access_policy.proto` + Listing 2 and guide example; live policies retrieved (E8) embed the reference-values bundle, but layer-by-layer pinning on a live policy was not parsed out and the program component is unobserved on live policies → degraded. |
| C2 | Per-transform access budgets (e.g. "at most 1 access") | **P** | Shown in the docs' worked example (fedsql_dp_group_by, ε ≤ 1.0987, δ ≤ 1e-8); live policies are binary FedSQL configs — budget values in a live policy not extracted/verified → degraded. |
| C3 | Workloads endorsed under published keys enumerable from the log | **P** | Census executed credential-free: 509,569 entries over 19 reconstructable keys, payloads hash-verified (E8 Exp A; verifier check 14); degraded by two unqueryable guide fingerprints, retention lapses, sampled classification on the large keys (§4.4 reasons (i)–(iii)). |
| C3b | Published endorsement-key inventory is complete | **T** | Vendor-asserted inventory; no outsider procedure can exclude unpublished keys; inventory already shows drift (two guide fingerprints match no current reference-values key). |
| C4 | Endorsement freshness window stated (90-day; not_before 2025-02-15) | **V** | Statement recomputed from artifacts: exemplar validity 45 days (verifier check 6), 90-day relative window parsed (check 7), `not_before_absolute` 2025-02-15 confirmed at gboard.txtpb lines 87–90. |
| C4b | Endorsement freshness window enforced | **T** | Enforcement inside TEEs, unobservable; split from C4 on exactly this line. |
| C5 | Historical policies retrievable (transparency over time) | **P** | Executed checks contradict retrievability in practice: Feb-2025 guide example payload + policy binary both HTTP 400; older KMS-layer payloads lapse on a gradient (E8 table; §4.5) → P as negative finding per rule 2 (the paper's own named case). |
| D1 | Endorsement keys published; rotation observable | **P** | Publication + fingerprints executed (all 30 reference-values key blocks recompute to their stated fingerprints, E8; verifier check 5 for the 9 Gboard keys); rotation only inferred — the 2025 baseline's key class is unverified → bundled claim is P. |
| D2 | Key custody (who holds the signing keys; compromise response) | **T** | The log shows usage, not custody; no outsider procedure reaches custody or the compromise-response process (monitoring detects usage of published keys, which is a different claim). |
| D3 | Upload encryption keys bound to policy; TTL enforced | **T** | TTL is "best-effort" by the vendor's own wording — unverifiable by definition; binding/enforcement is runtime behavior inside KMS/TEE. |
| E1 | Reference values pin stage0 firmware digests + SEV-SNP min SVN | **P** | Reference values are public and were parsed (E8 key extraction; stage0/kernel/stage1/system endorsements censused and payload-verified); the full check against a current live policy was not executed → degraded. (Row E1 = matrix section E, not experiment E1.) |
| E2 | Hardware root of trust (AMD/Intel) intact | **T** | No outsider procedure exists; trust in vendor attestation roots is the claim's whole basis. |
| F1 | Side-channel observability acknowledged as limitation | **V** | The claim *is* the disclosure; the disclosure was verified in the system paper (§3, §6.3) and blog, with the Snpeek citation → rule 1 V. |
| F2 | Sideloaded/proprietary logic protected against malicious operator via future hardware | **T** | Forward-looking claim about future hardware; no current mechanism and no outsider procedure today. |
| G1 | "Only metrics and DP model weights visible to workload operators" | **T** | Runtime visibility inside the pipeline is unobservable without device instrumentation + operator-side audit; fact-claim on vendor statement → rule 1. |
| G2 | Operator sees which uploads are used per round (§6.3 of Daly et al.) | **T** | The disclosure in §6.3 is verified, but the claim as worded is the visibility *fact*, which is unobservable → rule 1 (the F1/G2 contrast the rubric's disclosure rule was written for). |
| G3 | DP noise actually added as programmed; budget not exceeded at runtime | **T** | Noise addition is a runtime act; the `_MAX_ZCDP` guard is statically checkable in a policy but dynamic enforcement is unobservable — same enforcement class as A3/C4b. |
| G4 | GCP Confidential Space offload containers reproducible | **T** | The vendor's docs disclaim the property itself ("not guaranteed to be reproducible"); there is no degraded procedure to flag — the property is not provided. Retained as a scope limit on B2, not a vendor claim. |

## Blind distribution

**4 V / 10 P / 13 T over 27 rows** (V: A1, B1, C4, F1 · P: A2, B2, B3, B4,
C1, C2, C3, C5, D1, E1 · T: A3, A4, B5, C3b, C4b, D2, D3, E2, F2, G1, G2,
G3, G4). Derived from the evidence above before the row-by-row diff in
DIFF-AND-ADJUDICATIONS.md was compiled.
