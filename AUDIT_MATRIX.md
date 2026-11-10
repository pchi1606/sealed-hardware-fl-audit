# S3 Audit Matrix — verifiability of Google's sealed-hardware Gboard training pipeline
Target: arXiv:2609.31494 (Daly et al., v4 2026-09-30) + Google Research blog (2026-10-02)
Method: outsider audit — no device, no Google credentials, no private access.

## Scoring key
- **V (verified)**: outsider reproduced the check end-to-end with public artifacts.
- **P (partially checkable)**: checkable in principle; blocked or degraded in current infrastructure.
- **T (trust-required)**: no outsider procedure exists; must trust Google / vendor / operator.

## A. Attestation binding (device → KMS → TEE)

| # | Claim | Score | Evidence / procedure |
|---|---|---|---|
| A1 | KMS TEE software recorded in public transparency log (exemplar) | V | Rekor entry `108e9186e8c5677a4e8e…bd` (idx 1634041292, 2026-05-26) → endorsed hash `62e818ac…` → payload from `federatedcompute-pa.googleapis.com/data/transparency/sha2-256:62e818ac…`; sha256(payload)==endorsed hash **recomputed**. Inclusion proof verified at leaf index 1512137030 (the top-level `logIndex` 1634041292 is Rekor's virtual index across shards; difference = prior shards' 121,904,262 leaves); checkpoint signature, signed entry timestamp, and the endorsement statement's own signature all verified 2026-11-04 (E8). Earlier 'API self-contradiction' reading withdrawn — index-space error, corrected 2026-11-04. Claim wording clarified 2026-11-05 (manuscript fix round 8): as scored, this row is exemplar-scoped — the executed chain covers the guide's documented exemplar; for independently sampled entries only the entry→payload link is verified (manuscript §4.1/§5). |
| A2 | Devices validate KMS key + access policy via endorsements + inclusion proofs | P | Device-side flow; outsider cannot observe a device handshake. P under the manuscript §3 client-side rule: the deciding procedure — static inspection of the public client code path — was EXECUTED 2026-11-04 (E11, fix pass 7) on the local clone of google-parfait/federated-compute @ a9d5262a: `AttestationTransparencyVerifier` verifies the upload-key endorsement against the KMS verifying keys and the pipeline configuration against the policy verifying keys (`VerifySignedPayload`, with transparency-log inclusion required when the endorsement options set it), verifies Rekor inclusion by root-hash recomputation (`VerifyRekorLogEntry`), and cross-checks the policy digest carried in the key endorsement. What remains unobservable: production devices running this verifier. |
| A3 | KMS releases decryption keys only to TEEs matching policy reference values | T | Enforced inside KMS TEEs; no external observation point. (Code-inspectable: `kms/` in repo.) T under the same §3 rule: inspecting server code cannot decide runtime release behaviour inside operator TEEs. |
| A4 | Root→worker Noise channel with attestation check | T | Internal; paper §3.3.1. No public artifact. |

## B. Code transparency

| # | Claim | Score | Evidence / procedure |
|---|---|---|---|
| B1 | KMS + data-processing binaries built from public OSS source | V | `github.com/google-parfait/confidential-federated-compute`, Apache-2.0; build workflow `.github/workflows/build.yaml` + `reusable_build.yaml` public; run 26261649715 (success, sha `fe439180…`) verified via GitHub API. |
| B2 | Binaries reproducibly buildable (bit-identical) | P | **Executed instance 2026-11-04 (score P: the claim as worded covers all binaries; one was executed)**: the documented invocation (repo's Build-and-attest workflow: `cd kms && bazelisk run -c opt //:install_release_binaries`) run on a documented-class cloud env (Kaggle) at the pinned exemplar-era commit fe439180… completed (exit 0) and the produced `kms/container.tar` SHA-256 == endorsed digest `d14a1852…` exactly (E6 attempt 3). Corroboration: 20 SLSA-v1 attestations for the digest from 20 distinct commits, byte-identical subject; input-sensitivity across commits remains observational. Earlier attempts documented in E6-results (VM proxy block; two cloud attempts on an undocumented plain command — not results on the claim). Precision (fix pass 6): the working invocation is documented in the repo's public Build-and-attest workflow file — the workflow the provenance statements name as builder — not in the prose docs or the audit guide; the frozen protocol's own command failed at the era tree, so the executed result is an exploratory rescue of a failed frozen protocol, not a frozen-protocol confirmation (manuscript §4.3). |
| B3 | SLSA provenance for every endorsed binary on Rekor | P | Hash-index search returns 20 DSSE entries for `d14a1852…`; provenance bundles on GitHub API with builder/materials. |
| B4 | Workload Python programs inspectable (embedded in policy) | P | Paper Listing 2 shows the mechanism. Live policies ARE retrievable via the published policy endorsement keys (E8 census 2026-11-04: 509,185 policy-key entries; sampled payloads hash-verified): every sampled policy endorsement is an Oak statement with subject "policy" pointing to a binary-protobuf policy artifact. **E10 (2026-11-04, fix pass 7) recursive wire-format decode of all 57 distinct policy artifacts referenced by a fresh identically-sampled retrieval (149 served payloads, all hash-verified): 5 artifacts embed a complete Python workload program, base64-encoded — 3 distinct texts** (Gboard ACT training, 44,189 B decoded; Gboard HMM SentencePiece training, 32,314 B; AGSA/OmniEnt DP synthesis, 10,676 B), each carrying its `_MAX_ZCDP` guard in code; the other 52 contain no program text in any scanned form (plain, nested, or base64/hex-decoded; no compression or encryption markers in any field). The embedded-program mechanism is verified as documented AND observed on live policies. "Inspectable" here means inspectable by an external analyst applying recursive wire-format decoding: neither the policy bytes at surface level nor the vendor's documented string-level inspection path reveals the programs, and whether the deployed serving path itself decodes them was not tested. The programs' `_MAX_ZCDP` guard shows the program text self-limits a budget parameter; no claim is made that the guard's value matches any budget the surrounding policy states. P: program-carrying artifacts are the minority form (5 of 57); the large-key population is sampled. [Supersedes the E8 field-parse + string-scan non-detection, which could not see encoded content.] |
| B5 | Sideloaded proprietary logic stays private | T | By design not in the log. The vendor's assurance is that auditors can inspect *how* sideloaded inputs are used; the interface contracts that would make that inspection possible are not published, and the sideloaded artifacts themselves are not in the log, so for the no-device persona the distinction between privacy-relevant and merely proprietary sideloading is not decidable from public artifacts. What would decide it: published interface contracts, or a confinement argument that arbitrary sideloaded transforms remain inside the policy's clipping/accounting/output bounds — neither currently available. |

## C. Policy expressiveness

| # | Claim | Score | Evidence / procedure |
|---|---|---|---|
| C1 | Policy pins exact program + root/worker binary digests at 4 stack layers (firmware/kernel/system/container) | P | What was executed (stated fix pass 6): the pinning structure was verified against the published `access_policy.proto`, the system paper's Listing-2 worked policy, and the guides' printed examples — fetched public documents. Live Python-workload policy bytes were NOT executed: the guide's worked-example payloads have lapsed from the store (manuscript §4.5) and the retrieved live policies are binary configs without the program field (B4). P because the deciding procedure (fetch a live policy; check the pinning) exists and is retention-blocked in current infrastructure. |
| C2 | Per-transform access budgets (e.g., "at most 1 access") | P | Shown in docs' worked example (`fedsql_dp_group_by`, epsilon ≤ 1.0987, delta ≤ 1e-8) as printed; not executed on live bytes; same live-policy dependency as C1. |
| C3 | Workloads endorsed under published keys enumerable from the log | P | **Enumerated 2026-11-04 (E8)**: 509,569 entries over 19 published endorsement keys via the credential-free `POST /api/v1/index/retrieve` (the endpoint keyed by entry-signing key — which the exemplar entry's key identifiably is: the published application endorsement key ea0d1f8f…). Payloads verified as in E8 (320 matched, 0 mismatch). Completeness is judged on the index endpoint's returned entry set, not on whether every payload is still served (payload lapse is the §4.5 retention finding); the endpoint's returns were cross-checked against the log's signed tree on a seeded 24-entry sample across four keys in E13 (all inclusion proofs folded to their served checkpoint roots; all checkpoint signatures and SETs verified). P not V: completeness rests on the vendor-published key inventory (two guide fingerprints already stale — 6052f352/5f884b69 match no current reference-values key), payload retention lapses (§4.5), large-key payload classification sampled. **[History: originally P on F1's 'degraded search' framing; rescored T on 2026-11-04 on the mistaken premise that endorsement keys are not index keys (wrong-endpoint October attempt); rescored back to P the same day on the corrected record — see ADJUDICATIONS.md.]****
| C3b | Published endorsement-key inventory is complete | T | Vendor-asserted inventory; no outsider procedure can exclude unpublished keys; inventory already shows drift (two guide fingerprints match no current reference-values key). Added 2026-11-04 by splitting C3 under the paper's S7 predicate (review-seat adjudication). |
| C4 | Endorsement freshness window stated (90-day window; not_before_absolute 2025-02-15); enforcement inside TEEs unobservable | V | Validity windows recomputed from fetched endorsement (`notBefore 2026-05-26` → `notAfter 2026-07-10`); `signed_timestamp` restrictions confirmed in `access_policy_reference_values/gboard.txtpb` (lines 87–90) and `kms/reference_values/reference_values.txtpb`. | **[Superseded 2026-11-04 by the C4/C4b split: this row scores the window's statement (V); its enforcement is row C4b (T). An interim bundled rescoring to P was replaced by the split.]**
| C4b | Endorsement freshness window enforced | T | Enforcement inside TEEs, unobservable. Split from C4 2026-11-04 (statement vs enforcement, review-seat adjudication). T under the manuscript §3 client-side rule (fix pass 6): code inspection cannot decide runtime enforcement inside operator TEEs. |
| C5 | Historical policies retrievable (transparency over time) | P* | Retention is "≥1 year" (docs): Feb-2025 Gboard endorsement+policy now 404. Continuous monitoring is the only way to keep C3 checkable. *P\* = negative finding: the executed check contradicted the claim as worded (manuscript §3, rule two) — not a partial success.* |

## D. Key lifecycle

| # | Claim | Score | Evidence / procedure |
|---|---|---|---|
| D1 | Endorsement keys published; rotation observable | P | `gboard.txtpb` holds 9 keys (docs' 2025 example showed 1) — rotation/expansion is publicly visible. Fingerprints recomputed from DER. | **[Rescored V→P 2026-11-04 for the bundled claim: keys published + fingerprints recomputed is V-grade; rotation is only inferred (2025 baseline key class unverified), so the bundled claim is P, matching §4.2/§5/Table 4.]**
| D2 | Key custody (who holds the signing keys; compromise response) | T | Log shows *usage*, not custody. A compromised endorsement key yields arbitrary policies; detection depends on monitors watching the log by endorsement key — which works (rekor-monitor / index endpoint; E8) — but only for published keys and only while payloads are retained. Consequence rule applied to a compromise (manuscript §5): endorsements whose log inclusion precedes the compromise stand on their own proofs; endorsements first appearing after it are treated as unendorsed; the verifier bounds the window from the log's timestamps and re-checks chains relying on entries inside it. |
| D3 | Upload encryption keys bound to policy; TTL enforced | T | Two propositions share this row: (i) uploads are bound to their policy's key — a cryptographic binding, code-inspectable, whose enforcement runs inside the KMS TEEs and is unobservable; (ii) keys expire after their TTL — the KMS design itself grounds this only in replicated observations of an untrusted time source plus key erasure, and states the limitation explicitly, so elapsed-time assurance (not the binding) is the trust-required part. KMS RAFT rollback-protection is code-inspectable only. T under the manuscript §3 client-side rule (fix pass 6). |

## E. Firmware / boot chain

| # | Claim | Score | Evidence / procedure |
|---|---|---|---|
| E1 | Reference values pin stage0 firmware digests + SEV-SNP min SVN | P | Mechanism in Listing 2 + `reference_values.txtpb`; live check needs current policy. Oak stage0/kernel endorsements chain to `project-oak/oak` repo (docs walk through one example). |
| E2 | Hardware root of trust (AMD/Intel) intact | T | No outsider procedure; trust in vendor attestation roots. Paper acknowledges "subject to current-generation TEE limitations". |

## F. Side-channel surface

| # | Claim | Score | Evidence / procedure |
|---|---|---|---|
| F1 | Side-channel observability acknowledged as limitation | V | Paper §3 ("subject to known limitations such as side-channel observability"), §6.3, blog; cites Snpeek (Zhang et al., NDSS 2026). Honest scoping — counts as verified disclosure. |
| F2 | Sideloaded/proprietary logic protected against malicious operator via future hardware | T | Forward-looking; no current mechanism. |

## G. Operator-insider residual

| # | Claim | Score | Evidence / procedure |
|---|---|---|---|
| G1 | "Only metrics and DP model weights visible to workload operators" | T | Outsider cannot observe operator views. Would need device instrumentation + operator-side audit. |
| G2 | Operator sees *which uploads* are used per round (§6.3) | T | Disclosed in paper as known headroom cost (no sampling amplification). Verified disclosure. |
| G3 | DP noise actually added as programmed; budget not exceeded at runtime | T | Code inspectable; execution unobservable. The `_MAX_ZCDP` program guard (Listing 2) is checkable *statically* from the policy — dynamic enforcement is not. T under the manuscript §3 client-side rule (fix pass 6). |
| G4 | GCP Confidential Space offload containers reproducible | T | Docs explicitly carve out: "builds are also not guaranteed to be reproducible — verification relies on SLSA provenance via the GitHub Attestation API instead." Verified disclosure of a weaker link. |

## Threat-model rubric (who defeats what)

| Adversary | Defeated by (verified) | Residual |
|---|---|---|
| Honest-but-curious operator | A1, B1–B3, C4 (crypto binding of data to policy) | G1 (can't confirm), B5 (sideloaded logic opaque) |
| Malicious operator (active) | A3/A4 in principle (attestation-bound keys) | G3 (can't observe runtime), D2 (key compromise), F2 (side channels) |
| Compromised endorsement key | — (nothing; this is the trust anchor) | D2: detection only via log monitoring (currently degraded, F1) |
| Malicious workload author | B4/C1 in principle (policy pins exact program; auditors read it) | B5 (sideloaded code unaudited), G3 |
| TEE hardware attacker | E1 in principle (SVN thresholds) | E2, F1–F2 |
| Log operator (Sigstore) equivocation | Inclusion proofs; witnesses (standard) | C5 (availability/retention); F1 (search-index degradation is operational, not equivocation) |

## Comparator: Apple Private Cloud Compute (same rubric, abbreviated)

| Dimension | Google CFC (Gboard FL training) | Apple PCC (inference) |
|---|---|---|
| Transparency log | Rekor (independent operator); endorsements for binaries + policies | Apple-operated log; VRE tools verify consistency; device refuses unlogged builds |
| Source | Full OSS (Apache-2.0), incl. KMS + program executor | Partial source; full production image published as binaries |
| Reproducible builds | Claimed; 20/20 identical-binary attestations observed; SLSA on Rekor | **Explicitly not provided** (Apple docs; independently confirmed WiSec'26, arXiv:2605.24239) |
| Policy language | `DataAccessPolicy` protobuf: per-transform reference values, access budgets, config matchers, embedded programs | No per-workload policy language published; attestation↔log binding only |
| Key custody transparency | Endorsement keys + rotation in public repo | Apple-held keys; rotation via log |
| Training vs inference | Production **training** (Gboard next-word, DP) | **Inference** only; "data never trains models" |
| Third-party audit | This methodology (outsider, no device) | VRE + bug bounty + SOC 3; selected researchers had early access |

Takeaway for the paper: Google's deployment is strictly more ambitious on the *training* + *reproducibility* axes, and its "complete workload enumeration" is executable by published key (E8) — completeness bounded by the vendor's key inventory and payload retention — whereas Apple's narrower attestation↔log claim is operationally simpler to check. "Auditable" is a spectrum — the matrix makes the spectrum explicit.
