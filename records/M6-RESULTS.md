# M6 cross-route count reconciliation — RESULTS

Executed under AMENDMENT-2026-11-05 (frozen before the run).
Run completed: 2026-11-05.

- Candidate Google App policy (4d41c79b): index-returned total 12055, resolved 12055; minimal >=30-entry window [1088768850, 1088770281] span 1431, index count in window 61.
- Candidate Gboard policy 1 (3ebd2cd4): index-returned total 30913, resolved 30913; minimal >=30-entry window [517284007, 517286046] span 2040, index count in window 72.

Chosen key: Google App policy (4d41c79b); window [1088768850, 1088770281] (1432 indexes).
Accounting: returned-with-body 1432, empty-after-retries 0, error 0; accounted 1432/1432; window complete: True.
Bodies failing membership parse: 0; bodies of other keys: 1371.
Index-returned count in window I = 61; scan membership count S = 61.
Decision (amendment rule): No omission detected in the window (S == I).
Row C3c stays T regardless: a bounded window cannot prove global completeness of the index returns.

Provenance note (round-12 coordinator): the scan process's own final
file writes were lost to a filesystem-merge fault at process exit;
every number above is taken verbatim from the process's completion
output. Cross-checks: the scan's phase-1 values were independently
re-observed in the run log (totals 12055/30913, windows and in-window
counts identical), and a post-run re-resolution of the key's
index-returned list (2026-11-05: 12,057 UUIDs) filtered to the frozen
window returns exactly 61 logIndexes — the in-window set is stable
(the window is a historical region) and the hit list is reproducible
from the frozen window under the amendment's membership rule with
scripts/m6_scan.py.
