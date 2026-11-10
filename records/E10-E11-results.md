# E10 / E11 — wire-level policy-artifact decode; client-code inspection (2026-11-04, fix pass 7)

Run: 2026-11-04 evening (America/Chicago), public endpoints only,
sequential requests. Scripts: `e10_wire_decode.py`, `e10b_supplement.py`
(this directory). Raw outputs: `e10_wire_decode.json`,
`e10b_supplement.json`, `e10_statement_f8a4dc99.json`,
`e10_program_cedd3799.py`, `e10_program_33ef45b5.py`,
`e10_program_9a877855.py` (= 33ef45b5 text), `e10_program_2d4384e4.py`
(= cedd3799 text), `e10_program_f8a4dc99.py` (decoded program texts).

## E10 — recursive wire-format decode of retrieved policy artifacts

Motivation: the E8 classification (field-parse + whole-buffer string
scan) reported no embedded program and no `_MAX_ZCDP` in any retrieved
payload. A string scan cannot see encoded content; both review seats
pressed the point. E10 re-ran the E8 sampling for the six app policy
keys (exhaustive ≤120 entries, else 30 evenly spaced; + the guide's
named Gboard entry), fetched every served payload (hash-verified),
extracted every distinct policy-artifact digest, fetched each
artifact (hash-verified), and subjected it to a recursive protobuf
wire-format decode: every length-delimited field at every nesting
depth inventoried and scanned (raw bytes; per-field; base64- and
hex-decodings of every long encoded run; compression-magic scan).

Results (E10b robust pass; E10's first pass agrees on its subset):
- Served payloads: 149 of 159 attempted (PCS 30/30, Gboard 1 29/31 —
  1 payload HTTP 400 + 1 entry-fetch network failure; Gboard 2 0/8 —
  7 payload HTTP 400 + 1 entry-fetch failure; Google App 30/30;
  Pixel Search 30/30; Recorder 30/30). All served payloads
  hash-verified; zero mismatches.
- Distinct policy artifacts referenced: **57**; all 57 fetched,
  hash-verified, and wire-decoded.
- **Five artifacts embed a complete Python workload program,
  base64-encoded in a policy field — three distinct program texts:**
  - "A trusted program for Gboard ACT model training" (44,189 B
    decoded) — artifacts `cedd37998850…` (389,658 B, 4 sampled
    statement refs) and `2d4384e41a65…` (389,658 B, 1 ref);
  - "A trusted program for Gboard HMM SentencePiece model training"
    (32,314 B) — artifacts `33ef45b5c51d…` (49,166 B, 3 refs) and
    `9a877855e0ae…` (49,166 B, 4 refs);
  - "TEE-hosted DP synthetic data generation for AGSA / OmniEnt
    (Circle-to-Search)" (10,676 B) — artifact `f8a4dc99d473…`
    (20,313 B, Google App key, 8 refs; endorsing statements current,
    validity windows spanning 2026-08-27 → 2027-01-13).
  Each program carries its `_MAX_ZCDP` guard in code (the AGSA
  program: `_MAX_ZCDP = 0.416`, a computed-budget check against it,
  and a per-user record cap as its sensitivity control).
- The other 52 artifacts contain no program text in any scanned
  form (whole-buffer, per-field, or decoded) — binary protobuf
  configurations embedding the reference-values bundle, as E8 found.
- First-level payloads: no program markers in any form; no
  decoded-text fields.

**Consequence for row B4:** the embedded-program mechanism is not
merely documented — it is exercised on live endorsed policies,
including the flagship Gboard training workloads, and the embedded
programs are outsider-inspectable after decoding. B4's letter stays
**P** (sampling bound: 30 entries per large key; program-carrying
artifacts are the minority form, 5 of 57), but its basis flips from
a negative finding (non-detection) to a positive, qualified
observation. The E8-era statements "no retrieved payload was found
to contain an embedded program / _MAX_ZCDP" were true of the method
used (plain string scan) and are superseded by this decode.

## E11 — executed static inspection of the public client code path (row A2)

Local clone: google-parfait/federated-compute @
a9d5262aa05a4b1ff3c23697d644023c5d913840 (`code/fc-repo`).
Inspection executed 2026-11-04:
- `fcp/client/attestation/attestation_transparency_verifier.cc` —
  `AttestationTransparencyVerifier::Verify` (the client library's
  attestation verifier) calls `VerifySignedPayload` on (i) the
  upload encryption-key configuration against the configured KMS
  verifying keys and (ii) the pipeline configuration (access
  policy) against the access-policy verifying keys, and cross-checks
  that the access-policy SHA-256 carried in the encryption key's
  signature headers matches the pipeline configuration.
- `fcp/confidentialcompute/payload_transparency/payload_transparency.{h,cc}`
  — `VerifySignedPayload`: requires a signature chain terminating
  in a configured verifying key; when the endorsement options set
  `require_transparency_log_entry`, requires transparency-log
  inclusion of the final signature; enforces signature time
  constraints.
- `fcp/confidentialcompute/payload_transparency/rekor.cc` —
  `VerifyRekorLogEntry`: verifies the entry's data hash against the
  payload digest, the entry signature under a verifying key, the
  Merkle inclusion proof by root-hash recomputation (RFC 6962 audit
  path), and the checkpoint signature under the Rekor key.

**Consequence for row A2:** the inspection §3's fourth rule names
has now been executed: the published client library implements both
halves of the claimed validation (KMS key + access policy, via
endorsements and inclusion proofs) and binds the policy digest into
the key endorsement. What remains unobservable is deployment: that
production device builds run this verifier with log inclusion
required. A2 stays **P**; its basis changes from "procedure exists;
unexecuted" to "executed (static inspection, E11); deployment
unobservable", and it leaves §3's third rule's "unexecuted" class
(no row now sits in that class).
