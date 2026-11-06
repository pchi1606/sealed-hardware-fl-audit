# Second-scorer reliability exercise — PoPETs sealed-hardware FL audit

Independent second scoring of the condensed audit matrix (Table tab:matrix, 23 rows),
based only on the evidence presented in the manuscript itself (matrix anchors + Findings, §4–§5).
Scoring rubric as defined in the paper: V = verified by outsider execution;
P = partially checkable (sound in principle, degraded/blocked in practice);
T = trust-required (no outsider procedure).

| # | Row claim (short name) | Paper's score | My score | Agree/Disagree |
|---|---|---|---|---|
| 1 | KMS software in public log | P | P | agree |
| 2 | Device-side policy validation | P | P | agree |
| 3 | KMS key release only to matching TEEs | T | T | agree |
| 4 | OSS source + public build recipe | V | V | agree |
| 5 | Reproducible builds (bit-identical) | P | P | agree |
| 6 | SLSA provenance on Rekor per binary | P | P | agree |
| 7 | Policy-embedded programs inspectable | P | P | agree |
| 8 | Sideloaded logic stays private | T | T | agree |
| 9 | Policy pins program + 4-layer digests | P | P | agree |
| 10 | Per-transform access budgets | P | P | agree |
| 11 | Full workload set enumerable | P | T | disagree |
| 12 | 90-day freshness window stated | P | P | agree |
| 13 | Historical policies retrievable | P | P | agree |
| 14 | Endorsement keys + rotation public | P | P | agree |
| 15 | Key custody/compromise response | T | T | agree |
| 16 | Upload-key binding; "best-effort" TTL | T | T | agree |
| 17 | Reference values pin FW/SVN | P | P | agree |
| 18 | Hardware roots intact | T | T | agree |
| 19 | Limitations disclosed | V | V | agree |
| 20 | Operator sees only DP outputs | T | T | agree |
| 21 | Operator sees per-round upload use | P | T | disagree |
| 22 | Noise actually added; budget held | T | T | agree |
| 23 | GCP-offload reproducibility | T | T | agree |

**Raw agreement: 21/23**

## Notes on disagreements

- Row 11 — Full workload set enumerable (paper P, mine T): the paper itself calls enumeration "architecturally uncheckable" — Rekor has no endorsement-key index, the measured documented retrieval path runs ~9.7 entries/sec (~3 years for the 90-day window), and the only bulk alternative (BigQuery) requires GCP credentials, so no outsider procedure is actually presented.
- Row 21 — Operator sees per-round upload use (paper P, mine T): the anchor concedes the claim "rests on vendor word" (§6.3 of the vendor paper); no outsider procedure was executed or described, which is the same epistemic position as Row 20 (operator views), scored T.
