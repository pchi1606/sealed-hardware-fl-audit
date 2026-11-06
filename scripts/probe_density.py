#!/usr/bin/env python3
"""Round-12 design probe (pre-amendment measurement, NOT the experiment):
for each large census key, take the index endpoint's returned UUID list,
draw an evenly spaced sample, fetch those entries via the log route, and
measure (a) whether the membership rule (body fingerprint == queried key)
holds on the sample, (b) the logIndex density of the key's entries, to
size a bounded whole-log window scan.
"""
import base64, hashlib, json, re, glob, sys, time, urllib.request

API = "https://rekor.sigstore.dev/api/v1"
REPO = "/home/hatch/workspace/gap-papers/s3-sealed-audit/code/cfc-repo"
TARGETS = {
    "3ebd2cd4": "Gboard policy 1",
    "2bb537ad": "Private Compute Services policy",
    "5aac231c": "Recorder policy",
    "4d41c79b": "Google App policy",
}
SAMPLE = 100

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
    """Fingerprint of the entry-signing key as carried in the entry body.
    Returns (kind, fingerprint-or-None)."""
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

def main():
    keys = extract_keys()
    out = {}
    for prefix, label in TARGETS.items():
        fp = next((k for k in keys if k.startswith(prefix)), None)
        assert fp, prefix
        uuids = post_json(API + "/index/retrieve", {"publicKey": {"format": "x509", "content": base64.b64encode(pem_of(keys[fp]).encode()).decode()}})
        n = len(uuids)
        step = max(1, n // SAMPLE)
        sample = uuids[::step][:SAMPLE]
        rows = []
        kinds = {}
        match = 0
        for u in sample:
            e = get_json(API + f"/log/entries/{u}")[u]
            kind, bfp = body_fingerprint(e["body"])
            kinds[kind] = kinds.get(kind, 0) + 1
            ok = bfp is not None and bfp.startswith(prefix)
            match += ok
            rows.append({"uuid": u, "logIndex": e["logIndex"], "kind": kind, "fp_match": ok})
            time.sleep(0.15)
        rows.sort(key=lambda r: r["logIndex"])
        idx = [r["logIndex"] for r in rows]
        gaps = [b - a for a, b in zip(idx, idx[1:])]
        # projected minimal window holding >=30 key entries: use sample density.
        # sample is a 1-in-step thinning; a window containing s sampled entries
        # holds ~s*step key entries and spans (s-1)*local_gap_avg logIndexes.
        proj = None
        for s in range(2, len(idx)):
            need = -(-30 // step)  # sampled entries needed for ~30 key entries
            if s >= need:
                span = idx[s - 1] - idx[0]
                # slide for the tightest span of s sampled points
                span = min(idx[i + s - 1] - idx[i] for i in range(len(idx) - s + 1))
                proj = {"sampled_needed": s, "projected_key_entries": s * step, "projected_window_span": span}
                break
        out[prefix] = {"label": label, "index_count": n, "sampled": len(rows),
                       "kinds": kinds, "fp_match": match, "min_gap": min(gaps) if gaps else None,
                       "median_gap": sorted(gaps)[len(gaps) // 2] if gaps else None,
                       "sample_span": idx[-1] - idx[0] if idx else None, "projection": proj,
                       "sample_rows": rows}
        print(f"{label}: index={n} sampled={len(rows)} kinds={kinds} fp_match={match}/{len(rows)} "
              f"median_gap={out[prefix]['median_gap']} projection={proj}", file=sys.stderr)
    json.dump(out, open("/home/hatch/workspace/gap-papers/s3-sealed-audit/battery/panel-2026-11-05/round12/probe_density_out.json", "w"), indent=1)

if __name__ == "__main__":
    main()
