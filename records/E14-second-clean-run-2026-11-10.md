# E14 — Second clean run of the CI build invocation (2026-11-10)

Run record for the second clean run of the exemplar-era CI invocation
reported in Section 4.3 of the audit (row C2). Transcribed from the
Section 4.3 account; no separate build log was preserved for this run.
The documented record remains the first (2026-11-04) run's, whose
provenance, error log, and result are in records/E1 (and Appendix A of
the paper). This run is a same-auditor, same-route repetition of it,
not an independent reproduction.

- Date: 2026-11-10.
- Tree: a fresh clone of the exemplar-era commit
  `fe439180bb24e65ad46e869eddee88f9c9b34875` (same commit as the first
  run, so both run records describe the same tree).
- Working directory: inside `kms/` of the cloned tree.
- Invocation: `bazelisk run -c opt //:install_release_binaries --
  --destdir="$OUT"` (the documented CI invocation, verbatim).
- Exit status: 0.
- Result: the SHA-256 of the produced `container.tar` exactly equals
  the endorsed digest
  `d14a1852f08b528f9975245f300d44e2500aaff9c8a9c5572e0114b7203e3e47`
  (bit-for-bit reproduction). The digest value is the endorsed KMS
  digest as printed in the paper's Section 4.3 / Table 9 row C2 basis
  and as recorded in the artifact's `expected/expected.json`
  (`kms_digest`); this file records the equality of the two digests,
  not a new digest value.
- Host (self-reported by the environment): Ubuntu 24.04.5 (kernel
  6.18.55+), 4 vCPUs (Xeon @ 2.20 GHz), approx. 32 GB RAM, gcc 13.3.0,
  Bazel 8.2.1. The host publishes no resource class.
- Log note: no container or operating-system image digest was logged
  for this run (as for the first run), so neither run is reproducible
  to a specific image.
