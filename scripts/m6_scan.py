#!/usr/bin/env python3
"""M6 cross-route count reconciliation, executed under AMENDMENT-2026-11-05
(frozen before this run). Phase 1: resolve the complete index-returned
logIndex lists for the two candidate keys via the batched log-entries
route; compute each key's minimal contiguous window holding >=30 of its
entries; choose the smaller window. Phase 2: scan EVERY logIndex in the
window via the log route; membership = body public-key SHA-256 fingerprint
== target key. Checkpointed + resumable. Results -> M6-RESULTS.md.
"""
import base64, hashlib, json, re, glob, sys, time, urllib.request, urllib.error, os

API = "https://rekor.sigstore.dev/api/v1"
REPO = "/home/hatch/workspace/gap-papers/s3-sealed-audit/code/cfc-repo"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "m6_scan_state.json")
CANDIDATES = {"4d41c79b": "Google App policy", "3ebd2cd4": "Gboard policy 1"}
WINDOW_MIN_ENTRIES = 30
WINDOW_MAX_SPAN = 60000

def http(req):
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def post_json(url, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    return json.loads(http(req))

def get_json(url):
    return json.loads(http(urllib.request.Request(url, headers={"Accept": "application/json"})))

def extract_keys():
    files = glob.glob(REPO + "/kms/reference_values/*.txtpb") + glob.glob(REPO + "/access_policy_reference_values/*.txtpb")
    keys = {}
    for f in files:
        text = open(f).read()
        for m in re.finditer(r'raw:\s*"((?:\\x[0-9a-fA-F]{2}|[^"\\])*)"', text):
            s = m.group(1)
            der = bytes(int(s[i+2:i+4], 16) for i in range(0, len(s) - 3, 4) if s[i] == "\\" and s[i+1] == "x") if "\\x" in s else s.encode()
            keys[hashlib.sha256(der).hexdigest()] = der
    return keys

def pem_of(der):
    b = base64.b64encode(der).decode()
    lines = [b[i:i+64] for i in range(0, len(b), 64)]
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n"

def body_fingerprint(body_b64):
    try:
        body = json.loads(base64.b64decode(body_b64))
    except Exception:
        return ("unparseable", None)
    kind = body.get("kind")
    spec = body.get("spec", {})
    try:
        if kind in ("rekord", "hashedrekord"):
            pk = spec["signature"]["publicKey"]["content"]
            raw = base64.b64decode(pk)
            if raw.startswith(b"-----"):
                lines = [l for l in raw.decode().splitlines() if "---" not in l]
                raw = base64.b64decode("".join(lines))
            return (kind, hashlib.sha256(raw).hexdigest())
    except Exception:
        return (kind, None)
    return (kind, None)

def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, STATE)

def minimal_window(indexes, k):
    idx = sorted(indexes)
    best = None
    for i in range(len(idx) - k + 1):
        span = idx[i + k - 1] - idx[i]
        if best is None or span < best[0]:
            best = (span, idx[i], idx[i + k - 1])
    return best  # (span, lo, hi)

def phase1(st):
    keys = extract_keys()
    full = {}
    for prefix in CANDIDATES:
        for fp in keys:
            if fp.startswith(prefix):
                full[prefix] = fp
    st["candidates"] = {}
    partial_path = os.path.join(HERE, "m6_phase1_partial.json")
    partial = json.load(open(partial_path)) if os.path.exists(partial_path) else {}
    for prefix, name in CANDIDATES.items():
        fp = full[prefix]
        uuids = post_json(API + "/index/retrieve", {"publicKey": {"format": "x509", "content": base64.b64encode(pem_of(keys[fp]).encode()).decode()}})
        indexes = list(partial.get(prefix, []))
        done_batches = len(indexes) // 10
        indexes = indexes[:done_batches * 10]
        for j in range(done_batches * 10, len(uuids), 10):
            batch = uuids[j:j + 10]
            resp = post_json(API + "/log/entries/retrieve", {"entryUUIDs": batch})
            entries = resp.values() if isinstance(resp, dict) else resp
            for e in entries:
                if isinstance(e, dict) and "logIndex" not in e and len(e) == 1:
                    e = next(iter(e.values()))
                indexes.append(e["logIndex"])
            if (j // 10) % 100 == 0:
                partial[prefix] = indexes
                with open(partial_path, "w") as f:
                    json.dump(partial, f)
            time.sleep(0.05)
        partial[prefix] = indexes
        with open(partial_path, "w") as f:
            json.dump(partial, f)
        span, lo, hi = minimal_window(indexes, WINDOW_MIN_ENTRIES)
        inw = sum(1 for x in indexes if lo <= x <= hi)
        st["candidates"][prefix] = {"name": name, "fingerprint": fp, "index_total": len(uuids),
                                    "resolved": len(indexes), "window_span": span, "window_lo": lo,
                                    "window_hi": hi, "index_in_window": inw}
        save_state(st)
        print(f"phase1 {name}: total={len(uuids)} resolved={len(indexes)} window=[{lo},{hi}] span={span} in_window={inw}", flush=True)
    # choose smaller window
    best = min(st["candidates"].items(), key=lambda kv: kv[1]["window_span"])
    st["chosen_prefix"] = best[0]
    st["phase"] = "phase2" if best[1]["window_span"] <= WINDOW_MAX_SPAN else "deferred"
    save_state(st)
    print(f"chosen: {best[1]['name']} span={best[1]['window_span']} -> {st['phase']}", flush=True)

def phase2(st):
    c = st["candidates"][st["chosen_prefix"]]
    target = c["fingerprint"]
    lo, hi = c["window_lo"], c["window_hi"]
    if "scan" not in st:
        st["scan"] = {"next": lo, "returned": 0, "empty": 0, "error": 0,
                      "member_hits": [], "unparseable": 0, "other_key": 0}
    sc = st["scan"]
    for i in range(sc["next"], hi + 1):
        outcome = None
        for attempt in range(3):
            try:
                resp = get_json(API + f"/log/entries?logIndex={i}")
                if resp:
                    e = next(iter(resp.values()))
                    kind, bfp = body_fingerprint(e["body"])
                    if bfp is None:
                        sc["unparseable"] += 1
                    elif bfp == target:
                        sc["member_hits"].append(i)
                    else:
                        sc["other_key"] += 1
                    sc["returned"] += 1
                    outcome = "returned"
                else:
                    outcome = "empty"
            except urllib.error.HTTPError as ex:
                outcome = "empty" if ex.code == 404 else "error"
            except Exception:
                outcome = "error"
            if outcome == "returned":
                break
            time.sleep(1.0 * (attempt + 1))
        if outcome == "empty":
            sc["empty"] += 1
        elif outcome == "error":
            sc["error"] += 1
        sc["next"] = i + 1
        if i % 50 == 0:
            save_state(st)
        time.sleep(0.05)
    save_state(st)
    st["phase"] = "done"
    save_state(st)
    print(f"phase2 done: returned={sc['returned']} empty={sc['empty']} error={sc['error']} members={len(sc['member_hits'])} unparseable={sc['unparseable']}", flush=True)

def write_results(st):
    lines = ["# M6 cross-route count reconciliation — RESULTS",
             "",
             "Executed under AMENDMENT-2026-11-05 (frozen before the run).",
             f"Run completed: {time.strftime('%Y-%m-%d %H:%M %Z')}.",
             ""]
    for prefix, c in st["candidates"].items():
        lines.append(f"- Candidate {c['name']} ({prefix}): index-returned total {c['index_total']}, "
                     f"resolved {c['resolved']}; minimal >={WINDOW_MIN_ENTRIES}-entry window "
                     f"[{c['window_lo']}, {c['window_hi']}] span {c['window_span']}, index count in window {c['index_in_window']}.")
    if st["phase"] == "deferred":
        c = st["candidates"][st["chosen_prefix"]]
        lines += ["", f"OUTCOME: DEFERRED under the amendment's feasibility bound — the smaller "
                      f"minimal window spans {c['window_span']} logIndexes (> {WINDOW_MAX_SPAN}). "
                      "No scan executed; the manuscript's disclosure stands unchanged."]
    else:
        c = st["candidates"][st["chosen_prefix"]]
        sc = st["scan"]
        total_window = c["window_hi"] - c["window_lo"] + 1
        accounted = sc["returned"] + sc["empty"] + sc["error"]
        complete = (accounted == total_window and sc["empty"] == 0 and sc["error"] == 0)
        S = len(sc["member_hits"])
        I = c["index_in_window"]
        lines += ["", f"Chosen key: {c['name']} ({st['chosen_prefix']}); window [{c['window_lo']}, {c['window_hi']}] "
                      f"({total_window} indexes).",
                  f"Accounting: returned-with-body {sc['returned']}, empty-after-retries {sc['empty']}, "
                  f"error {sc['error']}; accounted {accounted}/{total_window}; window complete: {complete}.",
                  f"Bodies failing membership parse: {sc['unparseable']}; bodies of other keys: {sc['other_key']}.",
                  f"Index-returned count in window I = {I}; scan membership count S = {S}."]
        if not complete:
            verdict = "INCONCLUSIVE — window incomplete; no completeness statement about the window is made."
        elif S == I:
            verdict = "No omission detected in the window (S == I)."
        elif S > I:
            verdict = f"OMISSION DETECTED: scan found {S - I} more entries of the key in the window than the index returned."
        else:
            verdict = f"DISCREPANCY: scan membership count below index count by {I - S}."
        lines += [f"Decision (amendment rule): {verdict}",
                  "Row C3c stays T regardless: a bounded window cannot prove global completeness of the index returns."]
    with open(os.path.join(HERE, "M6-RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(HERE, "m6_scan_out.json"), "w") as f:
        json.dump(st, f, indent=1)
    print("\n".join(lines), flush=True)

def main():
    st = {}
    if os.path.exists(STATE):
        st = json.load(open(STATE))
        print(f"resuming: phase={st.get('phase')}", flush=True)
    if st.get("phase") in (None, "phase1"):
        st["phase"] = "phase1"
        phase1(st)
    if st.get("phase") == "phase2":
        phase2(st)
    write_results(st)

if __name__ == "__main__":
    main()
