# Amendment 2026-11-05 — S3 cross-route count reconciliation (FROZEN before any run)

Frozen: 2026-11-05, before execution. Raised by the round-11 referee panel
(M6: the manuscript discloses that no cross-route count reconciliation was
executed) and adjudicated in round 12 under amendment discipline: this
analysis was NOT in the frozen protocol; it is recorded here, in the track's
amendment chain, before any scan runs. All results are reported whichever
way they land; no result-dependent stopping, no selective reporting.
Procedures run from this VM against public endpoints only, within
published rate limits (sequential requests).

## Question (bounded form of row C3c's dependency)

Does the Rekor v1 index endpoint's returned entry set for a published
endorsement key omit entries that are present in the log's tree? This
amendment tests the bounded, decidable form: over one contiguous window of
logIndexes, does an independent route (the log-entries route, which does
not use the index) find exactly the entries the index route returns for
one key inside that window?

Row C3c stays T regardless of outcome: a bounded window cannot prove the
global completeness of the index's returns. The manuscript's disclosure
sentence is updated only to state what was executed and what it found,
verbatim from the results file.

## Membership rule (validated before freezing)

An entry belongs to key K iff the SHA-256 fingerprint of the public key
embedded in the entry body equals K. For kind `rekord` the key is at
`spec.signature.publicKey`; `hashedrekord` entries carry the key at the
same position. Validation (density probe, 2026-11-05, round12/
probe_density_out.json): 100 evenly spaced index-returned entries sampled
for each of four keys (Gboard policy 1, Private Compute Services, Recorder,
Google App) — 400/400 bodies matched their index-attributed key under this
rule; kinds were mixed rekord/hashedrekord in every sample.

## Design

1. Candidate keys: Google App policy (fingerprint prefix 4d41c79b, census
   12,051 entries) and Gboard policy 1 (3ebd2cd4, census 30,752). Fetch
   each key's COMPLETE index-returned logIndex list via
   `POST /api/v1/index/retrieve`.
2. Window: for each candidate, the minimal contiguous logIndex interval
   containing at least 30 of that key's index-returned entries, computed
   from the actual returned list (no projection). Choose the candidate
   with the smaller window.
3. Feasibility bound (fixed now): execute the scan only if the chosen
   window spans at most 60,000 logIndexes. Otherwise record a reasoned
   deferral with the measured window sizes and stop.
4. Scan: fetch EVERY logIndex in the window via
   `GET /api/v1/log/entries?logIndex=<i>` (the log route), sequentially,
   checkpointing progress to disk. Classify each index as:
   returned-with-body / empty-after-3-retries / error. Apply the
   membership rule to every returned body; count bodies that fail to
   parse separately (they are accounted, not silently dropped).
5. Accounting: every window index must end in exactly one class. Any
   unaccounted index, or any index left empty/error after retries, makes
   the window INCOMPLETE and no completeness statement about the window
   is made (the paper's own record notes this endpoint returned empty
   for a full day on 2026-10-05; an incomplete window is reported as
   inconclusive, not as agreement).

## Decision rule (reported verbatim either way)

Let I = the index-returned count of the chosen key inside the window
(>= 30 by construction) and S = the scan's membership count inside the
window.
- Window complete and S == I: "no omission detected in the window".
- Window complete and S > I: omission detected; report S - I and the
  offending logIndexes.
- Window complete and S < I: discrepancy; report both counts (possible
  causes include body-parse failures, counted separately above).
- Window incomplete: inconclusive; report the accounting.

## Execution record

Script: round12/m6_scan.py (checkpointed, resumable). Results:
round12/M6-RESULTS.md, copied into the deposit (records/) with this
amendment (deposit root) when the deposit is next re-pinned. The density
probe that sized this design: round12/probe_density.py +
probe_density_out.json (probe ran 2026-11-05, before this freeze's scan;
the probe made no count claim).
