#!/usr/bin/env python3
"""Offline verifier for the S3 sealed-hardware audit headline claims.

Author: Prabhu Rangaraju

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
    check("scan ~= 22.2 days @500/s",
          abs(window_entries / 500 / 86400 - 22.2) < 0.3,
          f"{window_entries / 500 / 86400:.1f}d")
    check("scan ~= 5.5 days @2000/s",
          abs(window_entries / 2000 / 86400 - 5.55) < 0.1,
          f"{window_entries / 2000 / 86400:.2f}d")
    check("scan ~= 3.5 TB @3.6KB/entry",
          abs(window_entries * 3600 / 1e12 - 3.45) < 0.1,
          f"{window_entries * 3600 / 1e12:.2f} TB")

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

    # -- 11. Key-indexed search failure (F4) --------------------------------
    ks = load("keysearch_bg_result.json")
    check("keysearch status documents failure",
          ks.get("status") == "timeout_or_fail", ks.get("status", "?"))

    # -- 12. Hash-index search artifact ------------------------------------
    hs = load("hashsearch_kms.json")
    check("hashsearch UUID list non-empty",
          isinstance(hs, list) and len(hs) > 0, f"n={len(hs)}")

    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)
    print("All headline claims verified against the bundled artifacts.")


if __name__ == "__main__":
    main()
