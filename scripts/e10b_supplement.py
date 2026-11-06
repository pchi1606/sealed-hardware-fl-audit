#!/usr/bin/env python3
"""E10b — supplement to E10: robust re-sampling, per-digest statement counts,
hex-decode rescan, full decoded-field inventory, and preservation of the
evidence chain for the artifact carrying an encoded embedded program
(digest f8a4dc99...).

Same endpoints and sampling as E8/E10 (exhaustive <=120 entries, else 30
evenly spaced; + the guide's named Gboard entry). Up to 3 attempts per
fetch; every failure status logged.
"""
import base64, hashlib, json, re, sys, time
import urllib.request, urllib.error
sys.path.insert(0, "battery/panel-2026-11-04")
from e10_wire_decode import (extract_keys, index_retrieve, walk,
                             printable_ratio, scan_blob, GUIDE_ENTRY)

REKOR = "https://rekor.sigstore.dev/api/v1"
TRANS = "https://federatedcompute-pa.googleapis.com/data/transparency/sha2-256:"
OUT = "battery/panel-2026-11-04"
SUSPECT = "f8a4dc99d473c836c80b501815979f9cae69b3f91f29adfa7df587ab86027d1a"
HEXRUN = re.compile(rb"[0-9a-fA-F]{64,}")
B64RUN = re.compile(rb"[A-Za-z0-9+/=]{64,}")

def http_get(url, tries=3):
    last = None
    for _ in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": "s3-audit-e10b"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = (e.code, e.read())
            if e.code == 400:
                return last
        except Exception as e:
            last = (-1, str(e).encode())
        time.sleep(1.0)
    return last

def decoded_texts(blob):
    """All (path, kind, bytes) decodings of long encoded runs inside
    printable length-delimited fields that yield mostly-printable text."""
    out = []
    for p, v in walk(blob):
        if v is None or len(v) < 64 or printable_ratio(v) < 0.98:
            continue
        for run in B64RUN.findall(v):
            try:
                dec = base64.b64decode(run)
            except Exception:
                continue
            if len(dec) >= 32 and printable_ratio(dec) > 0.85:
                out.append((p, "base64", dec))
        for run in HEXRUN.findall(v):
            if len(run) % 2: continue
            try:
                dec = bytes.fromhex(run.decode())
            except Exception:
                continue
            if len(dec) >= 32 and printable_ratio(dec) > 0.85:
                out.append((p, "hex", dec))
    return out

def main():
    keys = extract_keys()
    digest_refs = {}   # digest -> list of {key, uuid, integratedTime, validity}
    payload_blobs = []
    stats = {}
    failures = []
    for prefix, (der, label) in sorted(keys.items()):
        uuids = index_retrieve(der)
        total = len(uuids)
        if total <= 120:
            idxs = list(range(total))
        else:
            idxs = sorted({round(i * (total - 1) / 29) for i in range(30)})
        if prefix == "3ebd2cd4":
            for j, u in enumerate(uuids):
                if u.startswith(GUIDE_ENTRY):
                    idxs.append(j); break
        st = {"label": label, "entries": total, "attempted": 0, "served": 0,
              "http400": 0, "hash_ok": 0}
        for j in idxs:
            st["attempted"] += 1
            code, raw = http_get(f"{REKOR}/log/entries/{uuids[j]}")
            time.sleep(0.12)
            if code != 200:
                failures.append((label, uuids[j][:16], "entry", code)); continue
            entry = json.loads(raw)
            ebody = list(entry.values())[0]
            body = json.loads(base64.b64decode(ebody["body"]))
            h = body["spec"]["data"]["hash"]["value"]
            code2, payload = http_get(TRANS + h)
            time.sleep(0.12)
            if code2 == 400:
                st["http400"] += 1; continue
            if code2 != 200:
                failures.append((label, uuids[j][:16], "payload", code2)); continue
            st["served"] += 1
            if hashlib.sha256(payload).hexdigest() == h:
                st["hash_ok"] += 1
            payload_blobs.append(payload)
            subj, validity = None, None
            try:
                stmt = json.loads(payload)
                subj = stmt["subject"][0]["digest"]["sha256"]
                validity = stmt.get("predicate", {}).get("validity")
                if subj == SUSPECT:
                    with open(f"{OUT}/e10_statement_f8a4dc99.json", "w") as f:
                        json.dump(stmt, f, indent=1)
            except Exception:
                for p, val in walk(payload):
                    if val is None: continue
                    try:
                        stmt = json.loads(val)
                        subj = stmt["subject"][0]["digest"]["sha256"]
                        validity = stmt.get("predicate", {}).get("validity")
                        break
                    except Exception:
                        continue
            if subj:
                digest_refs.setdefault(subj, []).append(
                    {"key": label, "uuid": uuids[j],
                     "integratedTime": ebody.get("integratedTime"),
                     "validity": validity})
        stats[prefix] = st
        print(st, flush=True)

    print(f"distinct artifacts referenced: {len(digest_refs)}")
    print(f"failures: {failures}")
    suspect_refs = digest_refs.get(SUSPECT, [])
    print(f"statements pointing to suspect artifact: {len(suspect_refs)}")
    for r in suspect_refs:
        print("  ", r)

    # decode inventory over every distinct artifact + every first-level payload
    inventory = []
    all_blobs = []
    for dg in sorted(digest_refs):
        code, blob = http_get(TRANS + dg)
        time.sleep(0.12)
        if code == 200 and hashlib.sha256(blob).hexdigest() == dg:
            all_blobs.append((dg, blob))
    for blob in payload_blobs:
        all_blobs.append(("payload", blob))
    for name, blob in all_blobs:
        for p, kind, dec in decoded_texts(blob):
            hits, _ = scan_blob(dec)
            inventory.append({"in": name, "path": ".".join(map(str, p)),
                              "kind": kind, "decoded_bytes": len(dec),
                              "marker_hits": hits,
                              "first_line": dec[:100].decode("utf-8", "replace")})
    print(f"decoded-text fields found: {len(inventory)}")
    for inv in inventory:
        print("  ", inv["in"][:16], inv["path"], inv["kind"],
              inv["decoded_bytes"], inv["marker_hits"],
              repr(inv["first_line"][:60]))
    summary = {"payload_stats": stats, "failures": failures,
               "distinct_artifacts": len(digest_refs),
               "digest_ref_counts": {d: len(v) for d, v in digest_refs.items()},
               "suspect_refs": suspect_refs, "decoded_inventory": inventory}
    with open(f"{OUT}/e10b_supplement.json", "w") as f:
        json.dump(summary, f, indent=1)
    print("done")

if __name__ == "__main__":
    main()
