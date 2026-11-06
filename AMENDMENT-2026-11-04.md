# Amendment 2026-11-04 — S3 expansion experiments (FROZEN before any run)

Frozen: 2026-11-04, before execution. Ordered by the author (fix-all rule,
2026-11-04) in response to the test-40 full-text panel's NEW-WORK majors.
All results are reported whichever way they land; no result-dependent
stopping, no selective reporting. Procedures run from this VM against
public endpoints only, within published rate limits (sequential requests).
Anonymization of the manuscript is unaffected (experiments are artifact-side).

## E1 — Independently sampled Rekor entries (answers panel major 1)
Sampling rule (vendor-independent, fixed now): query
`POST rekor.sigstore.dev/api/v1/index/retrieve` with the entry-signing key
extracted from the exemplar entry (the procedure documented in §4.4 of the
paper). Take ALL returned entries, sort by logIndex ascending, and process
the first 10 whose body decodes to an endorsement-type entry with a
sha2-256 data hash. For each: (a) fetch the endorsement payload from
`federatedcompute-pa.googleapis.com/data/transparency/sha2-256:<hash>`;
(b) recompute SHA-256 of the payload and compare to the entry's endorsed
hash; (c) extract the subject digest from the payload. Report per-entry
PASS/FAIL and the failure rate over the processed set. If the endpoint or
key yields <10 endorsement entries, process all found and say so.

## E2 — Inclusion-proof adjudication (answers panel major 3)
Re-fetch the exemplar entry (UUID 108e9186…) today; re-verify the returned
inclusion proof with an implementation independent of the paper's original
one (a from-scratch RFC 6962 fold written for this amendment, validated on
synthetic trees of known root). Also try the Rekor v2 API entry endpoint if
available. Report: proof index vs entry logIndex, root match/mismatch, and
whether the contradiction persists, resolves, or changes form.

## E3 — Live policy fetch (answers panel major 4)
From E1's sampled entries and/or the reference-values file, identify the
most recent Gboard access-policy artifact reachable today; fetch its bytes
from the transparency store; if a policy is obtained, inspect it for (a) an
embedded Python program and (b) a `_MAX_ZCDP`-type guard, and report both
verbatim-relevant excerpts. If no current policy is reachable, report the
exact failure (endpoint, status) — a documented negative attempt.

## E4 — Input-sensitivity of the 20/20 identical digests (answers major 5)
For each of the 20 provenance commits (from the bundled SLSA artifacts),
query the GitHub API for the commit's changed-file list and classify
whether any changed path plausibly feeds the KMS build (paths under
`kms/`, root build files `WORKSPACE*`, `MODULE.bazel`, `.bazelrc`,
`build/` shared targets). Report per-commit classification and the count
of commits that did / did not touch KMS inputs.

## E5 — Measured enumeration throughput (answers panel major 6)
Time a bounded sequential retrieval of 100 consecutive log entries via
`POST /api/v1/log/entries/retrieve` (logIndexes), report measured
entries/sec and the implied scan window for ~958M entries at the measured
rate (single figure, labelled as a same-endpoint extrapolation). If the
endpoint fails, report that and keep the stipulated range, labelled as such.

## E6 — Reproducible build on documented class (answers panel major 2)
Documented class (4 CPU / 16 GB / 150 GB, unproxied) is not available on
this VM (2 vCPU / 7 GB, proxied; the original attempt failed pre-compilation,
exit 37). Per the standing rule, second-environment runs go to Kaggle or
Colab. This amendment freezes the attempt protocol (clone the public repo
at the exemplar commit, `bazelisk build -c opt //kms:main`, record exit
code, log tail, and — on success — the SHA-256 of the produced binary vs
d14a1852…). Execution requires the Kaggle/Colab route, which a generic
subagent cannot launch (no browser); the packaged attempt is handed to the
parent. Manuscript claims stay downgraded until E6 returns a result.

## Reporting
One results file per experiment in this directory (E1-results.md …
E6-results.md), written from the raw logs the same day. The manuscript is
updated only from those files, in a dated addendum pass; any result that
weakens a headline claim reframes the claim, never gets buried.
