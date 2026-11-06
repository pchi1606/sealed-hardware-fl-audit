# E13 — Index cross-check + sampled chain authentication (2026-11-04)

Question (panel demands M4/M6, in-house seat on 94dbce3e): the census's
509,569-entry figure is the index endpoint's return, whose completeness
the manuscript states it did not independently verify against the log's
tree; and chain authentication (inclusion proof, checkpoint, signatures)
had been executed only for the guide's worked exemplar.

Method: for four endorsement keys — Private Compute Services policy
`2bb537ad…` (largest), Recorder policy `5aac231c…`, Gboard policy key 1
`3ebd2cd4…`, and the application key `ea0d1f8f…` (the exemplar's key) —
the index endpoint's returned UUID list was re-fetched live and a
seeded sample drawn (Python `random.Random(20261104)`, 6 per key, 24
total). Each sampled entry was then fetched via the independent
log-entries route and checked, following the Experiment-B method of
the E8 record (openssl CLI; RFC 6962 folding implemented from scratch):

1. leaf hash = SHA-256(0x00 ‖ canonical body);
2. inclusion proof folds to the checkpoint root hash served with the
   proof (fold at the proof's own leaf index — the API's entry
   `logIndex` is the virtual index and does not fold, the E2 quirk,
   confirmed again here on all 24);
3. the checkpoint note's signature verifies under Rekor's published
   key, and the checkpoint's root/size agree with the proof's;
4. the Signed Entry Timestamp verifies over the sorted-key canonical
   JSON (body / integratedTime / logID / logIndex).

Index totals returned live this run: PCS 409,718 (identical to the
census figure), Recorder 52,049 (identical), Gboard key 1 30,878
(census: 30,752 — the log has grown since the census), application
key 115 (identical).

Result: **24 of 24 sampled entries pass all four checks** (24/24 leaf
folds, 24/24 checkpoint signatures, 24/24 checkpoint–proof
consistencies, 24/24 SETs). The index endpoint's returns are therefore
cross-checked against the log's signed tree on a seeded sample across
the size range, and chain authentication now extends beyond the
exemplar to 23 further entries under four keys. This bounds, but does
not eliminate, the inherited-completeness caveat: a sample cannot
prove the endpoint omits nothing, so the manuscript's sentence stands,
with this cross-check now cited beside it.

Script: `e13_crosscheck.py` (panel directory); raw per-entry results
in the run log (UUID, logIndex, proofIndex, four booleans per entry —
all true).
