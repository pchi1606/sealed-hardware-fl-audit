# Diff + adjudications — blind re-scoring vs the published matrix (build 04094abd)

Published matrix: manuscript Table 5 (Appendix C), stated by the manuscript
to mirror the artifact AUDIT_MATRIX.md; the two were cross-checked against
each other and against the §5 distribution text (full 4 V / 10 P / 13 T)
before diffing — they agree. Blind scores: SCORING-SHEET.md in this folder.

## Row-by-row diff

| Row | Published | Blind | Result |
|---|---|---|---|
| A1 | V | V | agree |
| A2 | P | P | agree (rule 3, flagged unexecuted) |
| A3 | T | T | agree — borderline, adjudicated below |
| A4 | T | T | agree — borderline, adjudicated below |
| B1 | V | V | agree |
| B2 | P | P | agree — borderline, adjudicated below |
| B3 | P | P | agree |
| B4 | P | P | agree (negative finding, rule 2) |
| B5 | T | T | agree |
| C1 | P | P | agree |
| C2 | P | P | agree |
| C3 | P | P | agree |
| C3b | T | T | agree |
| C4 | V | V | agree |
| C4b | T | T | agree |
| C5 | P | P | agree (negative finding, rule 2) |
| D1 | P | P | agree |
| D2 | T | T | agree |
| D3 | T | T | agree |
| E1 | P | P | agree |
| E2 | T | T | agree |
| F1 | V | V | agree |
| F2 | T | T | agree |
| G1 | T | T | agree |
| G2 | T | T | agree (disclosure-vs-fact, rule 1) |
| G3 | T | T | agree |
| G4 | T | T | agree — borderline, adjudicated below |

**Disagreements: none. No published score is wrong; no row changes.**

## Agreement statistics (computed honestly)

- Raw agreement: **27/27 = 100%**.
- Both marginals are identical (4 V / 10 P / 13 T), so chance-expected
  agreement Pe = (4² + 10² + 13²) / 27² = 285/729 ≈ 0.391.
- **Cohen's κ = 1.00** (n = 27, full matrix, artifact-level evidence).
- What this κ does and does not mean: it measures whether the *final,
  corrected* matrix is reproducible from its own artifact-level evidence
  under its own rubric — the exact question §3 raises. It does **not**
  retroactively validate the original scoring (the published matrix had
  already absorbed the earlier 23-row second-scorer exercise, κ = 0.85,
  and four panel fix passes before this exercise ran), and the scorer is
  an independent agent in the same tooling pipeline, not a human outside
  auditor. Both limits belong in the §3 disclosure (see
  S3-DISCLOSURE-DRAFT.md).

## Borderline rows — adjudications (score stands; reasoning recorded)

These are the rows where a competent blind scorer could land elsewhere;
each was decided on the rubric's own precedents, stated here so the
agreement above is auditable rather than asserted.

1. **A3 (T, not P).** Objection considered: A2 scores P under rule 3
   because a static-inspection procedure exists, and the KMS source is
   equally inspectable — so why is A3 not P-flagged? Adjudication: A2's
   claim is a client-side protocol-flow claim whose implementing artifact
   (the shipped client library) is itself the object of the check. A3's
   claim as worded is a universal negative about runtime key-release
   events inside KMS TEEs; source inspection shows the gating code
   exists, not that releases never bypass it. The matrix's own
   enforcement precedent is uniform — C4b (freshness enforcement) and D3
   (TTL enforcement) both score T on exactly this line, and §5 lists A3
   in the code-inspectable-but-unobservable runtime residual. **T stands.**
2. **A4 (T, not P).** Same class as A3: an internal enclave channel whose
   operation is a runtime fact; §5 groups it with A3 verbatim ("that the
   Noise root↔worker channel holds — all code-inspectable, none
   externally observable"). No public artifact exists for the channel
   itself. **T stands.**
3. **B2 (P, not V).** Objection considered: the one binary that carries
   the paper's worked chain was rebuilt bit-identically, so the row could
   be read as verified. Adjudication: the claim as worded covers the KMS
   *and* data-processing binaries; one instance was executed, the rest
   are unexecuted, and the paper's own single-instance scoping (applied
   to this row in fix pass 3) caps it at P. Rule 3 independently forbids
   V for the unexecuted remainder. **P stands.**
4. **G4 (T, not P-flagged).** Objection considered: rule 3 might suggest
   P for an unexecuted build-comparison procedure. Adjudication: the
   vendor's documentation disclaims the property itself ("builds are
   also not guaranteed to be reproducible"), so there is no degraded
   procedure standing between the auditor and a provided property —
   there is no property to check. Parallel to D3's "unverifiable by
   definition." The row functions as a stated scope limit on B2.
   **T stands.**

## Corrections list for the next consolidated fix pass

No score corrections — the matrix stands as published. The corrections
are disclosure and record hygiene:

**Manuscript (next fix pass):**
- **C-1 [REQUIRED — §3 is now factually stale].** §3 currently states
  that no artifact-level re-scoring has been done and "That stronger
  exercise remains undone." As of this report that is false. Replace
  with the completed-exercise disclosure drafted in
  S3-DISCLOSURE-DRAFT.md (same folder). Until this lands, the paper
  understates its own reliability record — the opposite error from the
  one §3 was written to avoid, but still an error.
- **C-2 [consistency, no text change needed if C-1 uses the draft].**
  The κ = 0.85 paragraph should keep its existing scoping ("κ does not
  characterize the published matrix") and be explicitly superseded *for
  the final matrix* by the new exercise, not deleted — the 0.85 figure
  is the honest record of the exercise as run at the time.

**Artifact record (AUDIT_MATRIX.md — not the manuscript, but Table 5
declares the manuscript's scores are "as in the artifact", so drift here
would matter):**
- **C-3.** The C5 score cell reads "T→P". Clean it to "P" so the
  artifact record states one unambiguous score per row.
- **C-4.** The C4 cell carries a stale bracketed note ("Rescored V→P
  2026-11-04: the bundled claim says 'enforced'…") that contradicts the
  final split recorded in fix pass 4 (C4 = the statement, V; C4b =
  enforcement, T). Annotate the note as superseded by the C4/C4b split
  or remove it, so the artifact does not contradict the paper it backs.
