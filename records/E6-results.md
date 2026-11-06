# E6 — Reproducible build on documented class: results

Protocol: AMENDMENT-2026-11-04.md (E6), frozen 2026-11-04 before any run.
Package: E6-kaggle/ (README + kaggle_e6_build.py). Target: `bazelisk build
-c opt //kms:main`; on success, SHA-256 of the produced binary vs the
endorsed KMS digest d14a1852f08b528f9975245f300d44e2500aaff9c8a9c5572e0114b7203e3e47.

## Attempt 1 — 2026-11-04, 16:58 CST (Kaggle) — DID NOT EXECUTE THE DOCUMENTED BUILD

- Environment: Kaggle kernel "E6 Kaggle Build",
  Kaggle kernel URL withheld in the anonymized copy (account identifier) — internet ON,
  CPU instance (~4 vCPU / 30 GB, at/above the documented class except disk).
- Script: kaggle_e6_build.py run **unmodified**.
- Clone of google-parfait/confidential-federated-compute: succeeded.
  Bazelisk download: succeeded.
- Bazel step, decisive log lines:
  - `+ /tmp/bazelisk build -c opt //kms:main`
  - `no such package 'kms': Package is considered deleted due to --deleted_packages`
  - `Build did NOT complete successfully`
  - `BUILD EXIT: 1` (Bazel elapsed 39.641s; cell total 49.927s)
- No ARTIFACT line; no SHA-256 produced. This was **not** a resource or
  session cutoff: the run completed quickly and failed at target resolution.

### Interpretation (plain)

The v1 script cloned the repository's **current default HEAD**
(`git clone --depth 50`, no checkout). At the current HEAD the `kms`
package has been deleted upstream, so `//kms:main` no longer resolves.
The frozen protocol specifies the build **at the exemplar commit** — the
exemplar-era state of the repo. Attempt 1 therefore never checked out the
code the documented build refers to: it did not execute the documented
build of the exemplar-era code, and it is **not a result on the claim**
(neither for nor against reproducible buildability). The build claim
stays at its current downgraded strength: provenance-only / observational
(20/20 identical attestations), matrix row B2 unchanged in substance
(score P).

## Exemplar-era commit — identified from track records

`fe439180bb24e65ad46e869eddee88f9c9b34875`

- Head SHA of GitHub Actions run 26261649715 ("Build and attest,"
  conclusion success) — the run the paper's worked audit (§4.2) cites in
  the exemplar endorsement's provenance chain; AUDIT.md records it as
  verified present among the 20 attestation commits (MATCH).
- Earliest of the 20 provenance commits for digest d14a1852…, dated
  2026-05-22T00:41:59Z (TEST_RESULTS.md; logs/commit_dates_20261008.json);
  the exemplar endorsement itself was integrated 2026-05-26.
- E4 classification (E-results.md): fe439180 is the **only** one of the 20
  provenance commits that touches KMS build inputs (kms/BUILD,
  kms/MODULE.bazel[.lock]).
- Spot-verified 2026-11-04 against the public repo: `kms/BUILD` at this
  commit defines `rust_binary(name = "main", …)` — `//kms:main` resolves
  at this commit.

## Attempt 2 — prepared, not launched

Corrected script: `E6-kaggle/kaggle_e6_build_v2.py` — identical to v1
except the clone is a full clone followed by
`git checkout fe439180bb24e65ad46e869eddee88f9c9b34875` (with the checked-out
HEAD printed to the log). Same target `//kms:main`, same bazelisk, same
5-hour timeout, same artifact walk and digest comparison.
Launch is the parent's Kaggle/browser route (standing rule); not launched
by this agent. Manuscript §4.3 and the summary-matrix anchor for the
reproducible-builds claim were updated 2026-11-04 to record attempt 1
honestly; the appendix row B2 (claim + score P only) is unchanged, as is
the claim's strength.

## Attempt 2 — 2026-11-04, ~17:19 CST (Kaggle) — SAME FAILURE AT THE ERA COMMIT

- Environment: Kaggle kernel "E6 build attempt 2",
  Kaggle kernel URL withheld in the anonymized copy (account identifier) — v2 script run
  **unmodified**.
- Log confirms `CHECKED OUT HEAD:
  fe439180bb24e65ad46e869eddee88f9c9b34875` — the pinned exemplar-era
  commit was actually checked out this time.
- Bazel step: `BUILD EXIT: 1` (Bazel elapsed 27.997s; cell total 42.528s),
  with the **same** error as attempt 1: `no such package 'kms': Package is
  considered deleted due to --deleted_packages`; `Build did NOT complete
  successfully`. No ARTIFACT line; no SHA-256 produced. Not a resource or
  session cutoff.

### Observation

The deleted-packages block exists **at the era commit too** — it is a
property of the era tree's own configuration, not of the current HEAD.
Attempt 1's interpretation is accordingly narrowed: tracking current HEAD
was not the (only) defect; the plain command fails at the exemplar-era
tree for the same reason.

## What the frozen protocol specifies (verbatim check, 2026-11-04)

AMENDMENT-2026-11-04.md (E6) freezes the attempt protocol as: "clone the
public repo at the exemplar commit, `bazelisk build -c opt //kms:main`,
record exit code, log tail, and — on success — the SHA-256 of the produced
binary vs d14a1852…". The protocol specifies the **plain command**
literally; it does **not** say "the documented build as given in the
project's own documentation". V1/v2 therefore faithfully executed the
frozen protocol — but the protocol's command is not the project's
documented build invocation (below).

## Era-tree inspection (fe439180…, cloned locally 2026-11-04)

- **No `deleted_packages` line exists in any rc file.** A grep for
  `deleted_packages` across the entire era tree returns nothing: neither
  the root `.bazelrc` nor `kms/.bazelrc` sets it (the root `.bazelrc`
  contains build flags, sanitizer configs, and the `cfc-remote` /
  `parfait-remote` configs only). The block comes from the root
  **`.bazelignore`**, which at fe439180 lists `kms` among its ignored
  directories (alongside `registry`, `containers/gcp`,
  `program_containers`, etc.). Bazel surfaces `.bazelignore` exclusions
  with exactly this error text ("Package is considered deleted due to
  --deleted_packages").
- **kms is a standalone Bazel module**, nested inside the repo but
  excluded from the root module by that `.bazelignore` entry: it has its
  own `kms/MODULE.bazel`, `kms/.bazelrc`, and `kms/.bazelversion` (8.2.1).
  From the root module, `//kms:main` cannot resolve, at any commit with
  this `.bazelignore`. Inside the kms module, the binary is the root
  package target `//:main` (`rust_binary(name = "main", …)` in
  `kms/BUILD`).
- **The project's own build invocation for KMS differs from the plain
  command.** The repo's "Build and attest" workflow
  (`.github/workflows/build.yaml` — the workflow in the paper's own
  provenance chain) lists `kms` as a module root
  (`- {root: kms, name: kms}`), and `.github/workflows/reusable_build.yaml`
  builds each module root with:

  ```
  cd kms && bazelisk run -c opt --curses=no --noshow_progress \
      --lockfile_mode=error //:install_release_binaries \
      -- --destdir="<output dir>"
  ```

  on a `large-4cpu-16gbRAM-150gbSSD` runner (the documented runner
  class). `//:install_release_binaries` (kms/BUILD) installs
  `:app_bundle` — an OCI/container bundle wrapping `:main` — renamed to
  `kms/container.tar` in the destination directory. The root README's
  generic `./scripts/build.sh release` builds only the root module's
  `//:install_all_binaries`, whose binary list at this commit contains no
  KMS artifact; neither `docs/`, `kms/README.md`, nor `CONTRIBUTING.md`
  gives any other KMS build command.

### Outcome: (a) — a documented invocation exists and differs

The documented (CI) invocation above replaces the plain command for
attempt 3. Corrected script: `E6-kaggle/kaggle_e6_build_v3.py` — same
clone + pinned checkout as v2, then the workflow invocation verbatim
(from inside `kms/`, with `--destdir=/kaggle/working/binaries`), and the
artifact walk retargeted to that destination directory (plus the
container tar's members and the kms `bazel-bin` output), since that is
where the documented build places its output (`kms/container.tar`, the
app_bundle of `//:main`) instead of `bazel-bin/kms`. Protocol note: v1
and v2 used the frozen protocol's plain `bazelisk build -c opt
//kms:main`, an undocumented invocation for this module layout; their
failures are results on that command only, not on the documented build,
which remains unexecuted. Launch of v3 is the parent's Kaggle/browser
route; not launched by this agent.

## Attempt 3 (documented invocation) — SUCCEEDED (2026-11-04, parent-run Kaggle route)

Kaggle kernel run of kaggle_e6_build_v3.py unmodified (parent's browser
route; result reported by the parent and recorded in MEMORY.md the same
day): checkout at the pinned era commit fe439180…, documented invocation
from inside kms/ (bazelisk run //:install_release_binaries), **BUILD EXIT:
0**, and the produced `kms/container.tar` has SHA-256 **d14a1852…** — an
EXACT MATCH with the endorsed KMS binary digest
d14a1852f08b528f9975245f300d44e2500aaff9c8a9c5572e0114b7203e3e47.
E6's success criterion is met: the documented build, executed by an
outsider on a documented-class environment, reproduces the endorsed
binary bit-for-bit (the app_bundle container tar is the endorsed artifact
form). Claim consequence: matrix row B2 (reproducible builds) is verified
by execution for the exemplar-era tree at the pinned commit; §4.3 and the
matrix are updated in the Perplexity fix round. Scope note: one execution,
one commit; input-sensitivity across the other 19 provenance commits
remains observational.

### Attempt 3 — primary run details (parent handoff, 2026-11-04 19:01 CST)
Kaggle kernel: Kaggle kernel URL withheld in the anonymized copy (account identifier)
Run window 5:28–6:34 PM CST (~36 min build). Pinned era commit
fe439180bb24e65ad46e869eddee88f9c9b34875 confirmed by git rev-parse.
Documented invocation (cd kms && bazelisk run -c opt
//:install_release_binaries) → BUILD EXIT: 0, 3,813 actions. Produced
container.tar SHA-256 =
d14a1852f08b528f9975245f300d44e2500aaff9c8a9c5572e0114b7203e3e47 —
EXACT MATCH with the endorsed KMS digest; also matched at
cfc/kms/bazel-bin/app_bundle.tar (its source). Positive result on the
documented-build claim. Folded into the manuscript in the Perplexity fix
round (§4.3, both matrices, AUDIT_MATRIX B2 → V; builds 572dfd7e →
987c2827).
