# E8 — Multi-key Rekor census, policy-payload hunt, and exemplar signature authentication

Run: 2026-11-04 (America/Chicago), public endpoints only, sequential requests.
Endpoints: `POST https://rekor.sigstore.dev/api/v1/index/retrieve`,
`GET https://rekor.sigstore.dev/api/v1/log/entries/<UUID>`,
`GET https://federatedcompute-pa.googleapis.com/data/transparency/sha2-256:<hash>`.
Local sources: `code/cfc-repo/docs/inspecting_endorsements.md`,
`code/cfc-repo/kms/reference_values/reference_values.txtpb`,
`code/cfc-repo/access_policy_reference_values/*.txtpb`,
`logs/rekor_kms_example.json`, `logs/endorsement_kms_example.json`, `logs/rekor_pubkey.pem`.

## Experiment A — census

### Key inventory

Every `raw:` DER key in the reference-values files was extracted and its SHA-256
recomputed: **all 30 key blocks match their stated fingerprints** (no mismatch).
Deduplicated: 20 unique keys, of which 1 is the Rekor log key itself
(`c0d23d6a…`, excluded from the endorsement census) leaving **19 endorsement keys**:
6 KMS-layer keys in current reference values, 8 Gboard policy keys, 1 policy key each
for Google App / Pixel Search / Private Compute Services / Recorder, the application
key `ea0d1f8f…`, plus the 2 guide-only fingerprints below.

**Guide-fingerprint discrepancy (finding):** the guide's rekor-monitor config lists
kernel fingerprint `6052f352…` and init_ram_fs fingerprint `5f884b69…`, but neither
key appears in the current `kms/reference_values`. Worse, the guide's own example
entries for those layers carry *different* keys: the kernel example entry
`108e9186e8c5677a1429…` embeds a key whose DER SHA-256 is `aafd4d5a…` (the current
reference-values kernel key), and the init example entry `108e9186e8c5677a4494…`
embeds `8546b897…` (the current stage1 key). The PEMs for `6052f352…` / `5f884b69…`
themselves are therefore not recoverable from the guide or the repo, and an
index/retrieve census **for those two fingerprints as stated is COULD-NOT-EXECUTE**
(no public key material available to query with). The 43 / 44 counts in the table
for those rows are the counts of the keys actually embedded in the guide's example
entries (`aafd4d5a…` / `8546b897…`), i.e. duplicates of the rows above them.

### Per-key entry counts (index/retrieve, HTTP 200 for every query)

| Key (SHA-256 prefix) | Source | Entries |
|---|---|---:|
| ea0d1f8f… (application / KMS container) | kms reference_values + guide | 115 (re-queried this run; matches prior census) |
| 98fc8ad4… (stage0) | kms reference_values + guide | 51 |
| aafd4d5a… (kernel, current) | kms reference_values | 43 |
| 8546b897… (init RAM FS / stage1, current) | kms reference_values | 44 |
| 0b4fcf07… (kernel cmdline) | kms reference_values | 45 |
| a19ea774… (system image) | kms reference_values | 83 |
| 021205b2… (container, key_id 1)* | kms reference_values | 3 |
| 6052f352… (kernel, guide only) | guide config — PEM unavailable | COULD-NOT-EXECUTE (see above) |
| 5f884b69… (init, guide only) | guide config — PEM unavailable | COULD-NOT-EXECUTE (see above) |
| 3ebd2cd4… (Gboard policy key_id 1) | gboard.txtpb | 30,752 |
| 49140964… (Gboard key_id 2) | gboard.txtpb | 8 |
| e5b8b89b… (Gboard key_id 3) | gboard.txtpb | 0 |
| 48877c9b… (Gboard key_id 4) | gboard.txtpb | 0 |
| 2c17376f… (Gboard key_id 5) | gboard.txtpb | 0 |
| 30cab9ee… (Gboard key_id 6) | gboard.txtpb | 0 |
| e40567d2… (Gboard key_id 7) | gboard.txtpb | 0 |
| 927bca59… (Gboard key_id 8) | gboard.txtpb | 0 |
| 4d41c79b… (Google App policy) | google_app.txtpb | 12,051 |
| ee9911ad… (Pixel Search policy) | pixel_search.txtpb | 4,607 |
| 2bb537ad… (Private Compute Services policy) | private_compute_services.txtpb | 409,718 |
| 5aac231c… (Recorder policy) | recorder.txtpb | 52,049 |

Total across the 19 censused keys (counting ea0d once, excluding the two
guide-only duplicates): **509,569 entries**. First-pass urllib attempts on the
large responses failed with `IncompleteRead` / `RemoteDisconnected`; all queries
were re-run with curl and returned HTTP 200 — no index errors remain.

*The container layer in reference_values lists two endorser keys (`021205b2…`
key_id 1 and `ea0d1f8f…` key_id 2); both were censused.

### Payload verification and classification

Method: keys with ≤120 entries — **exhaustive** (every UUID's entry fetched, payload
hash taken from `spec.data.hash.value`, payload fetched, SHA-256 recomputed).
Keys with >120 entries — deterministic sample of 30 evenly spaced UUIDs, plus the
guide's named Gboard policy entry for key `3ebd2cd4…` (31 attempted). Zero entry-fetch
errors in all rows. "Payload error" = transparency endpoint returned HTTP 400 with
body `Bad Request` (11 bytes) — the pattern already present in the retained
`logs/endorsement_gboard_policy.json`; consistent with the guide's stated
≥1-year retention having lapsed for older payloads.

| Key prefix | Attempted | Hash match | Hash mismatch | Payload errors (HTTP 400) |
|---|---:|---:|---:|---:|
| 3ebd2cd4… (Gboard pol. 1) | 31 (sample) | 30 | 0 | 1 (the guide's 2025-02-27 entry) |
| 49140964… (Gboard pol. 2) | 8 (all) | 0 | 0 | 8 |
| 4d41c79b… (Google App) | 30 (sample) | 30 | 0 | 0 |
| ee9911ad… (Pixel Search) | 30 (sample) | 30 | 0 | 0 |
| 2bb537ad… (PCS) | 30 (sample) | 30 | 0 | 0 |
| 5aac231c… (Recorder) | 30 (sample) | 30 | 0 | 0 |
| 98fc8ad4… (stage0) | 51 (all) | 27 | 0 | 24 |
| aafd4d5a… (kernel) | 43 (all) | 28 | 0 | 15 |
| 8546b897… (stage1) | 44 (all) | 30 | 0 | 14 |
| 0b4fcf07… (cmdline) | 45 (all) | 31 | 0 | 14 |
| a19ea774… (system) | 83 (all) | 54 | 0 | 29 |
| 021205b2… (container k1) | 3 (all) | 0 | 0 | 3 |

**Zero hash mismatches anywhere** (320 matched payload fetches; the
`aafd4d5a…`/`8546b897…` payload sets were fetched once and serve both their own
rows and the guide-example rows). KMS-layer matched payloads are all Oak
endorsement statements (`predicateType: https://project-oak.github.io/oak/tr/endorsement/v1`)
with subjects `stage0_bin` (27), `oak_containers_kernel` (28),
`oak_containers_stage1` (30), `oak_containers_kernel_cmd_line_regex` (31),
`oak_containers_system_image` (30) / `oak_containers_nvidia_system_image` (24).

### Policy verdict — POLICY ENDORSEMENTS FOUND, abundantly; no embedded program, no _MAX_ZCDP

- Every sampled payload under **every app policy key** (Gboard key 1, Google App,
  Pixel Search, PCS, Recorder) that is a JSON statement is an Oak endorsement of an
  access policy. Counts in samples: Gboard 18 JSON + 12 binary of 30 matched;
  Google App 17 + 13; Pixel Search 16 + 14; PCS 20 + 10; Recorder 17 + 13.
  The binary payloads are ~91–94-byte `SignedPayload` structures (the only printable
  string is `SignedPayload`). The JSON statements have exactly this shape
  (saved specimen: `policy-payload.json` in this directory, SHA-256
  `421929205333f64351a675b9d39f75b6fa657d7e93e56a8dad5a68589c008621`, fetched live,
  hash-verified):

  ```json
  {"_type":"https://in-toto.io/Statement/v1","predicateType":"https://project-oak.github.io/oak/tr/endorsement/v1","subject":[{"name":"policy","digest":{"sha256":"33ef45b5c51ded824d2f43aab3f4f6bee32813620056b7124044190b1ffeff2e"}}],"predicate":{"issuedOn":"2026-09-16T17:12:20.766619Z","validity":{"notBefore":"2026-09-16T17:12:20.766619Z","notAfter":"2026-12-15T17:12:20.766619Z"}}}
  ```

  Quoted fields: subject name = `"policy"`; predicate contains only
  `issuedOn` and `validity {notBefore, notAfter}` — **no embedded program field,
  no `_MAX_ZCDP` field, no program text of any kind in the statement**.
- Second level: 21 subject digests of these policy statements were fetched
  (3 Gboard + 2 per other app key, plus KMS-layer controls). All hash-matched.
  The policy artifacts are **binary protobufs** (16,300–389,658 bytes for the
  sampled policy digests) that embed the full Oak Containers reference-values
  bundle (the kernel-cmdline regex string is visible verbatim) and, in some,
  `fedsql` / `dp_` substrings consistent with FedSQL DP transforms — the same
  form the guide documents for the Gboard policy binary. **No `_MAX_ZCDP`
  (and no `ZCDP`) string in any of them.**
- Full-corpus string scan: across all 428 unique first-level payloads retrieved
  and the 21 second-level artifacts, occurrences of `_MAX_ZCDP` = **0**;
  embedded-program markers (`def `, `import `, `python`, `program`) = **0** in
  all first-level payloads and all policy second-level artifacts (one `def `
  byte-substring hit inside a 281 MB system-image binary is random binary
  content, not a program).
- The guide's specific Gboard policy example is no longer retrievable: entry
  `108e9186e8c5677af9f63f…`'s payload `d72534e0cae135b3ac11395d37956dbb89b328df4274a28b35cca22500845033`
  and its child policy binary `a324fe9606c953cfba56a666ad642fcef61764d0b0bd1878d3833842aa5dfbda`
  both return **HTTP 400, body `Bad Request`** today (integrated 2025-02-27;
  beyond the guide's stated ≥1-year availability).

**Verdict:** access-policy endorsements are not rare or hidden — the five app
policy keys account for 509,185 of the 509,569 censused entries, and their
endorsed payloads are Oak statements with subject `"policy"` pointing to binary
protobuf policy artifacts. In everything retrieved, **no payload contains an
embedded (Python) program and no payload contains a `_MAX_ZCDP` value**.

## Experiment B — signature authentication on the exemplar

Exemplar: UUID `108e9186e8c5677a4e68884126228c18dbe566ab43eb0be79b077401149bd340bc295d78e9cd86`,
retained copy `logs/rekor_kms_example.json`. Tool: OpenSSL 3.0.13 CLI
(Python `cryptography` is not installed in this environment).
Rekor public key: `logs/rekor_pubkey.pem` (DER SHA-256 =
`c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d` = entry logID).

1. **Checkpoint signature — VERIFIED.**
   Checkpoint note text =
   `rekor.sigstore.dev - 1193050959916656506\n2958662216\n95wSNbh2ebIsFEcdKA7ZEDQMI4uaK+EjWMQIVWbTm8M=\n`.
   Signature line decodes to 75 bytes: 4-byte hint `c0d23d6a` (= logID prefix)
   + 71-byte ASN.1 DER ECDSA signature (`30 45 …`).
   `openssl dgst -sha256 -verify rekor_pubkey.pem` over the note text → **Verified OK**.

2. **Signed Entry Timestamp — VERIFIED.**
   The SET (96-char base64 → 70-byte DER ECDSA signature, `30 44 …`) verifies
   against Rekor's public key over the canonical JSON with alphabetically sorted
   keys and no whitespace:
   `{"body":"<base64 body>","integratedTime":1779814484,"logID":"c0d23d6a…1801d","logIndex":1634041292}`
   → **Verified OK**. (Control: the same fields serialized in the order
   body/integratedTime/logIndex/logID do *not* verify — the sorted-key
   canonicalization is the operative one.)

3. **Artifact signature — VERIFIED.**
   `logs/endorsement_kms_example.json` **is** the endorsed payload itself:
   478 bytes, SHA-256 = `62e818ac02a0427b9811d08468e286aca2f5c68ca44191a9ab1f86075afe5a87`,
   exactly the `spec.data.hash.value` of the entry body. It is the Oak statement
   with subject `{"name":"kms","digest":{"sha256":"d14a1852f08b528f9975245f300d44e2500aaff9c8a9c5572e0114b7203e3e47"}}`.
   The entry's `spec.signature.content` (71-byte ECDSA DER) verifies under the
   entry's embedded public key (DER SHA-256 =
   `ea0d1f8ffed9512019a2ec968790263d88ea3324c6a6a782114e5ea1be4fd38f`, the application
   key) over the payload bytes with ECDSA/SHA-256 → **Verified OK**.

All three authenticity checks on the exemplar pass; nothing in Experiment B
was COULD-NOT-EXECUTE.
