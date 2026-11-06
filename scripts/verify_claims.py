#!/usr/bin/env python3
"""Offline verifier for the S3 sealed-hardware audit headline claims.

Recomputes every headline number in the manuscript from the bundled raw
artifacts in ../data/ (stdlib only -- no third-party dependencies) and
compares each against ../expected/expected.json. Prints PASS/FAIL per
check and exits non-zero if any check fails.

Run:  python3 scripts/verify_claims.py   (from the package root)
"""

import base64
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EXPECTED = json.loads((ROOT / "expected" / "expected.json").read_text())

results = []


def check(name, ok, detail=""):
    """Record one check and print its PASS/FAIL line."""
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def load(name):
    """Load a bundled JSON artifact from data/."""
    return json.loads((DATA / name).read_text())


def main():
    exp = EXPECTED

    # -- 1. Endorsed payload hash: sha256 of the endorsement file --------
    raw = (DATA / "endorsement_kms_example.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    check("endorsement sha256 == endorsed hash",
          digest == exp["endorsed_sha256"], digest[:16] + "...")

    # -- 2. Subject digest inside the endorsement statement ---------------
    endo = json.loads(raw)
    subj = endo["subject"][0]["digest"]["sha256"]
    check("endorsement subject digest == KMS binary digest",
          subj == exp["kms_digest"], subj[:16] + "...")

    # -- 3. Rekor entry identity ------------------------------------------
    rekor = load("rekor_kms_example.json")
    uuid = exp["rekor_uuid"]
    entry = rekor.get(uuid)
    ok = entry is not None
    check("rekor entry present", ok, uuid[:16] + "...")
    if ok:
        check("rekor logIndex", entry["logIndex"] == exp["rekor_log_index"],
              str(entry["logIndex"]))
        # integratedTime is a Unix timestamp in the Rekor response.
        its = datetime.fromtimestamp(entry["integratedTime"],
                                     tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        check("rekor integratedTime", its == exp["rekor_integrated_time"], its)

    # -- 4. SLSA attestations: 20 bundles, one builder, one digest --------
    atts = load("gh_attestation_kms.json")["attestations"]
    check("attestation count == 20", len(atts) == 20, f"n={len(atts)}")
    digests, commits, builders, btypes = set(), set(), set(), set()
    for att in atts:
        payload = att["bundle"]["dsseEnvelope"]["payload"]
        stmt = json.loads(base64.b64decode(payload))
        digests.add(stmt["subject"][0]["digest"]["sha256"])
        bd = stmt["predicate"]["buildDefinition"]
        for dep in bd.get("resolvedDependencies", []):
            gc = dep.get("digest", {}).get("gitCommit")
            if gc:
                commits.add(gc)
        builders.add(stmt["predicate"]["runDetails"]["builder"]["id"])
        btypes.add(bd["buildType"])
    check("all 20 subject digests == KMS digest",
          digests == {exp["kms_digest"]}, f"{len(digests)} distinct")
    check("20 distinct git commits", len(commits) == 20, f"n={len(commits)}")
    check("single builder id", builders == {exp["builder_id"]})
    check("single buildType", btypes == {exp["build_type"]})

    # -- 5. Endorsement keys: 9 P-256 keys, fingerprints recomputed -------
    txt = (DATA / "gboard.txtpb").read_text()
    raws = re.findall(r'raw: "((?:[^"\\]|\\x[0-9a-fA-F]{2})*)"', txt)
    fps = []
    for r in raws:
        der = bytes(int(r[i + 2:i + 4], 16)
                    for i in range(0, len(r), 4) if r[i:i + 2] == "\\x")
        # Guard against a malformed escape parse: DER must start 30 59.
        fps.append(hashlib.sha256(der).hexdigest() if der[:2] == b"\x30\x59"
                   else "PARSE_ERROR")
    check("key block count == 9", len(raws) == 9, f"n={len(raws)}")
    check("9 unique fingerprints", len(set(fps)) == 9)
    check("first fingerprint matches",
          fps and fps[0] == exp["first_key_fp"], (fps[0][:16] if fps else "?"))

    # -- 6. Endorsement validity window == 45 days -------------------------
    validity = endo["predicate"]["validity"]
    nb = datetime.fromisoformat(validity["notBefore"].replace("Z", "+00:00"))
    na = datetime.fromisoformat(validity["notAfter"].replace("Z", "+00:00"))
    days = (na - nb).days
    check("endorsement validity == 45 days", days == 45, f"{days} days")

    # -- 7. Freshness acceptance window == 90 days -------------------------
    m = re.search(r"not_before_relative:\s*\{\s*seconds:\s*(-?\d+)", txt)
    rel_days = abs(int(m.group(1))) // 86400 if m else None
    check("freshness window == 90 days", rel_days == 90, f"{rel_days} days")

    # -- 8. Log-scale and enumeration arithmetic --------------------------
    per_day = exp["log_total_entries"] / exp["log_window_days"]
    check("growth ~= 10.6M/day",
          abs(per_day - 10_600_000) / 10_600_000 < 0.01,
          f"{per_day:,.0f}/day")
    check("growth ~= 123/sec",
          abs(per_day / 86400 - 123.2) / 123.2 < 0.01,
          f"{per_day / 86400:.1f}/s")
    window_entries = 90 * per_day
    check("90-day window ~= 958M entries",
          abs(window_entries - 958_000_000) / 958_000_000 < 0.02,
          f"{window_entries:,.0f}")
    # The two stipulated-rate figures below are the audit's ORIGINAL October
    # estimate, retained only so the superseded arithmetic stays checkable.
    # The manuscript marks them superseded ("should not be cited"): the
    # measured rate is the next check.
    check("SUPERSEDED Oct estimate: scan ~= 22.2 days @500/s (stipulated)",
          abs(window_entries / 500 / 86400 - 22.2) < 0.3,
          f"{window_entries / 500 / 86400:.1f}d")
    check("SUPERSEDED Oct estimate: scan ~= 5.5 days @2000/s (stipulated)",
          abs(window_entries / 2000 / 86400 - 5.55) < 0.1,
          f"{window_entries / 2000 / 86400:.2f}d")
    check("SUPERSEDED Oct estimate: scan ~= 3.5 TB @3.6KB/entry",
          abs(window_entries * 3600 / 1e12 - 3.45) < 0.1,
          f"{window_entries * 3600 / 1e12:.2f} TB")
    # Measured naive-path rate (2026-11-04 experiment, manuscript S4.4):
    # batched sequential retrieval via log/entries/retrieve, 100 entries in
    # 10.3 s = ~9.7 entries/s, single run, no variance estimate. At that
    # rate the 90-day window takes ~1,142 days (~3 years). This is the
    # naive path's cost, NOT the enumeration route's (key-indexed census,
    # check 14).
    measured_days = window_entries / 9.7 / 86400
    check("naive scan at measured ~9.7/s ~= 1,142 days (~3 yr) for window",
          abs(measured_days - 1142) < 60,
          f"{measured_days:,.0f}d")

    # -- 9. Build recipe fields -------------------------------------------
    recipe = (DATA / "reusable_build.yaml").read_text()
    check("recipe machine type",
          "large-4cpu-16gbRAM-150gbSSD-ubuntu24.04" in recipe)
    check("recipe lockfile mode", "--lockfile_mode=error" in recipe)
    check("recipe retention-days: 5",
          re.search(r"retention-days:\s*5\b", recipe) is not None)

    # -- 10. Documented build-attempt failure ------------------------------
    blog = (DATA / "build_kms_attempt.log").read_text()
    check("build log: NoSuchElementException", "NoSuchElementException" in blog)
    check("build log: doTunneling", "doTunneling" in blog)
    check("build log: EXIT=37", "EXIT=37" in blog)

    # -- 11. Key-indexed search, first pass (F4) ---------------------------
    # The October first pass used the wrong endpoint (entries/retrieve with
    # an endorsement-key PEM) and timed out; this file records that attempt.
    # The corrected route is index/retrieve -- see check 14 (census).
    ks = load("keysearch_bg_result.json")
    check("keysearch record documents the October wrong-endpoint attempt",
          ks.get("status") == "timeout_or_fail", ks.get("status", "?"))

    # -- 12. Hash-index search artifact ------------------------------------
    hs = load("hashsearch_kms.json")
    check("hashsearch UUID list non-empty",
          isinstance(hs, list) and len(hs) > 0, f"n={len(hs)}")

    # -- 14. All-keys census (2026-11-04, E8) -------------------------------
    cz = load("census_2026-11-04.json")
    check("census counts sum to recorded total",
          sum(cz["counts_by_key_prefix"].values()) == cz["total_entries"] == 509569,
          str(cz["total_entries"]))
    check("exemplar key census count (ea0d1f8f)",
          cz["counts_by_key_prefix"]["ea0d1f8f"] == 115)

    # -- 15. Printed-value checks (round 15, 2026-11-05) --------------------
    # The sections above recompute numbers from the bundled data/ but never
    # read the compiled paper. This section parses the printed manuscript
    # (pdftotext -layout) and verifies the values a reader actually sees:
    # the full-matrix tally recounted row by row from printed Table 2, the
    # condensed tally via the printed caption plus the merge rule applied
    # to that recount, Cohen's kappa recomputed from the published
    # confusion-matrix marginals against its printed rounding, and the
    # section-5 variant cells. Manuscript resolution: $S3_MANUSCRIPT_PDF,
    # else ../popets-conversion/main-popets-draft.pdf (in-tree layout),
    # else the package's own paper.pdf. If no manuscript or no pdftotext
    # is available the section reports SKIP and does not fail the run.
    import os
    import subprocess
    from collections import Counter
    pr = exp["printed"]
    pdf = os.environ.get("S3_MANUSCRIPT_PDF")
    if not pdf:
        sib = ROOT.parent / "popets-conversion" / "main-popets-draft.pdf"
        if sib.exists():
            pdf = str(sib)
        elif (ROOT / "paper.pdf").exists():
            pdf = str(ROOT / "paper.pdf")
    ptxt = None
    if pdf:
        try:
            r = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                ptxt = r.stdout
        except (OSError, subprocess.SubprocessError):
            ptxt = None
    if ptxt is None:
        print("[SKIP] printed-value checks -- no manuscript PDF / pdftotext")
    else:
        norm = re.sub(r"\s+", " ", ptxt).replace("\U0001d705", "\u03ba")
        plines = ptxt.split("\n")
        cap = next((i for i, l in enumerate(plines)
                    if "Table 2: Full audit matrix (29 rows)" in l), None)
        rowpat = re.compile(
            r"^\s*([A-G]\d(?:b|c)?)\s+.*?[\s]{2,}(V|P|T)(\*|\u2020)?\s*(\\|$|\s{2,})")
        rows = {}
        if cap is not None:
            for l in plines[cap:]:
                m = rowpat.search(l)
                if m and m.group(1) not in rows:
                    rows[m.group(1)] = m.group(2)
        cnt = Counter(rows.values())
        fm = pr["full_matrix"]
        check("printed full matrix recount == 4/10/15 over 29",
              len(rows) == fm["rows"] and cnt["V"] == fm["V"]
              and cnt["P"] == fm["P"] and cnt["T"] == fm["T"],
              f"{cnt['V']}/{cnt['P']}/{cnt['T']} over {len(rows)}")
        cm = pr["condensed_matrix"]
        merged = Counter(rows.values())
        for rid in ("A4", "F2"):
            if rid in rows:
                merged[rows[rid]] -= 1
        check("printed condensed tally == 4/10/13 over 27 (caption + merges)",
              "4 V, 10 P, 13 T" in norm and merged["V"] == cm["V"]
              and merged["P"] == cm["P"] and merged["T"] == cm["T"]
              and len(rows) - 2 == cm["rows"],
              f"{merged['V']}/{merged['P']}/{merged['T']} over {len(rows) - 2}")
        kp = pr["kappa"]
        n = kp["n"]
        po = kp["agree"] / n
        pe = sum(a * b for a, b in zip(kp["marginals_first"],
                                       kp["marginals_second"])) / (n * n)
        kval = (po - pe) / (1 - pe)
        check("printed kappa: 21/23, recomputed 0.848, printed 0.85",
              f"{kp['agree']} of {n}" in norm
              and abs(kval - kp["value"]) < 0.001
              and f"\u03ba = {kp['printed']}" in norm
              and f"{round(kval, 2):.2f}" == kp["printed"],
              f"kappa={kval:.3f}")
        missing = [c for c in pr["variant_cells"] if c not in norm]
        check("printed section-5 variant cells present", not missing,
              "missing: " + ", ".join(missing) if missing else "all present")

    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)
    print("All headline claims verified against the bundled artifacts.")


if __name__ == "__main__":
    main()
