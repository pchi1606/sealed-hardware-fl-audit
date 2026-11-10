#!/usr/bin/env python3
"""E10 — wire-level protobuf decode of retrieved access-policy artifacts.

Replicates the E8 (2026-11-04) census sampling for the six app policy keys,
fetches the served payloads, extracts every distinct policy-artifact digest,
fetches each artifact, and subjects it to a recursive protobuf wire-format
decode: every length-delimited field at every nesting depth is inventoried
and scanned. Question (manuscript row B4): could an embedded program or a
_MAX_ZCDP value hide inside the retrieved policy artifacts in encoded or
nested form that the E8 field-parse + whole-buffer string scan would miss?

Endpoints (credential-free, as E8):
  POST https://rekor.sigstore.dev/api/v1/index/retrieve
  GET  https://rekor.sigstore.dev/api/v1/log/entries/<UUID>
  GET  https://federatedcompute-pa.googleapis.com/data/transparency/sha2-256:<hash>
Sequential requests, 0.15 s pacing.
"""
import base64, hashlib, json, math, re, subprocess, sys, time
import urllib.request, urllib.error

REKOR = "https://rekor.sigstore.dev/api/v1"
TRANS = "https://federatedcompute-pa.googleapis.com/data/transparency/sha2-256:"
CF = "code/cfc-repo/access_policy_reference_values"
KEYS_WANTED = {  # fingerprint prefix -> label
    "3ebd2cd4": "Gboard policy 1", "49140964": "Gboard policy 2",
    "4d41c79b": "Google App policy", "ee9911ad": "Pixel Search policy",
    "2bb537ad": "Private Compute Services policy", "5aac231c": "Recorder policy",
}
GUIDE_ENTRY = "108e9186e8c5677af9f63f"  # guide's named Gboard policy entry (prefix)
MARKERS = [b"_MAX_ZCDP", b"ZCDP", b"import ", b"def ", b"python", b"lambda",
           b"print(", b"program"]
MAGICS = {b"\x1f\x8b": "gzip", b"\x78\x01": "zlib", b"\x78\x9c": "zlib",
          b"\x78\xda": "zlib", b"\xfd7zXZ\x00": "xz", b"\x28\xb5\x2f\xfd": "zstd",
          b"BZh": "bzip2", b"\x04\x22\x4d\x18": "lz4"}
B64RUN = re.compile(rb"[A-Za-z0-9+/=]{64,}")

def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "s3-audit-e10"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()

def index_retrieve(der):
    b64 = base64.b64encode(der).decode()
    pem = ("-----BEGIN PUBLIC KEY-----\n" + "\n".join(
        b64[i:i+64] for i in range(0, len(b64), 64))
        + "\n-----END PUBLIC KEY-----")
    content = base64.b64encode(pem.encode()).decode()
    body = json.dumps({"publicKey": {"format": "x509", "content": content}})
    out = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{REKOR}/index/retrieve",
         "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, timeout=600)
    return json.loads(out.stdout)

def extract_keys():
    keys = {}
    for fn in ["gboard.txtpb", "google_app.txtpb", "pixel_search.txtpb",
               "private_compute_services.txtpb", "recorder.txtpb"]:
        text = open(f"{CF}/{fn}").read()
        for m in re.finditer(r'raw:\s*"((?:\\x[0-9a-fA-F]{2}|[^"\\])*)"', text):
            esc = m.group(1)
            der = bytes(int(esc[i+2:i+4], 16) for i in range(0, len(esc), 4)
                        if esc[i:i+2] == "\\x") if "\\x" in esc else esc.encode()
            fp = hashlib.sha256(der).hexdigest()
            if fp[:8] in KEYS_WANTED:
                keys[fp[:8]] = (der, KEYS_WANTED[fp[:8]])
    return keys

# ---------- protobuf wire format ----------
def parse_fields(buf, depth=0, max_depth=12):
    """Yield (path, field_no, wire_type, value_bytes_or_int). LEN values are
    also recursed into when they parse cleanly as a nested message."""
    fields, i, n = [], 0, len(buf)
    while i < n:
        start = i
        # tag varint
        tag, shift = 0, 0
        while True:
            if i >= n: return fields, False
            b = buf[i]; i += 1
            tag |= (b & 0x7F) << shift; shift += 7
            if not (b & 0x80): break
            if shift > 35: return fields, False
        fno, wt = tag >> 3, tag & 7
        if fno == 0: return fields, False
        if wt == 0:
            val, shift = 0, 0
            while True:
                if i >= n: return fields, False
                b = buf[i]; i += 1
                val |= (b & 0x7F) << shift; shift += 7
                if not (b & 0x80): break
                if shift > 70: return fields, False
            fields.append((fno, wt, val))
        elif wt == 1:
            if i + 8 > n: return fields, False
            fields.append((fno, wt, buf[i:i+8])); i += 8
        elif wt == 5:
            if i + 4 > n: return fields, False
            fields.append((fno, wt, buf[i:i+4])); i += 4
        elif wt == 2:
            ln, shift = 0, 0
            while True:
                if i >= n: return fields, False
                b = buf[i]; i += 1
                ln |= (b & 0x7F) << shift; shift += 7
                if not (b & 0x80): break
                if shift > 35: return fields, False
            if i + ln > n: return fields, False
            fields.append((fno, wt, buf[i:i+ln])); i += ln
        else:
            return fields, False
        _ = start
    return fields, i == n

def walk(buf, path=(), depth=0):
    """Inventory of every field; LEN fields recursed when clean-parsing."""
    out = []
    fields, ok = parse_fields(buf)
    if not ok and depth > 0:
        return out
    for fno, wt, val in fields:
        p = path + (fno,)
        if wt == 2:
            out.append((p, val))
            if depth < 12:
                sub, subok = parse_fields(val)
                if subok and sub:
                    out.extend(walk(val, p, depth + 1))
        else:
            out.append((p, None))
    return out

def printable_ratio(b):
    if not b: return 1.0
    good = sum(1 for c in b if 32 <= c < 127 or c in (9, 10, 13))
    return good / len(b)

def entropy(b):
    if not b: return 0.0
    from collections import Counter
    cnt = Counter(b); n = len(b)
    return -sum((c / n) * math.log2(c / n) for c in cnt.values())

def scan_blob(blob):
    hits = {m.decode(): blob.count(m) for m in MARKERS if blob.count(m)}
    magics = [name for magic, name in MAGICS.items() if magic in blob]
    return hits, magics

def main():
    keys = extract_keys()
    print(f"keys found: {sorted(keys)}", flush=True)
    digests = {}          # sha256 -> {keys:set, size}
    payload_stats = {}
    for prefix, (der, label) in sorted(keys.items()):
        uuids = index_retrieve(der)
        total = len(uuids)
        if total <= 120:
            sample = list(range(total))
        else:
            sample = sorted({round(i * (total - 1) / 29) for i in range(30)})
        idxs = list(sample)
        if prefix == "3ebd2cd4":
            for j, u in enumerate(uuids):
                if u.startswith(GUIDE_ENTRY):
                    idxs.append(j); break
        st = {"label": label, "entries": total, "attempted": 0, "served": 0,
              "http400": 0, "hash_ok": 0, "json": 0, "binary": 0}
        for j in idxs:
            st["attempted"] += 1
            code, raw = http_get(f"{REKOR}/log/entries/{uuids[j]}")
            time.sleep(0.15)
            if code != 200: continue
            entry = json.loads(raw)
            body = json.loads(base64.b64decode(
                list(entry.values())[0]["body"]))
            h = body["spec"]["data"]["hash"]["value"]
            code2, payload = http_get(TRANS + h)
            time.sleep(0.15)
            if code2 == 400:
                st["http400"] += 1; continue
            if code2 != 200: continue
            st["served"] += 1
            if hashlib.sha256(payload).hexdigest() == h:
                st["hash_ok"] += 1
            subj = None
            try:
                stmt = json.loads(payload)
                subj = stmt["subject"][0]["digest"]["sha256"]
                st["json"] += 1
            except Exception:
                st["binary"] += 1
                for p, val in walk(payload):
                    if val is None: continue
                    try:
                        stmt = json.loads(val)
                        subj = stmt["subject"][0]["digest"]["sha256"]
                        break
                    except Exception:
                        continue
            if subj:
                d = digests.setdefault(subj, {"keys": set(), "size": None})
                d["keys"].add(label)
        payload_stats[prefix] = st
        print(f"{label}: {st}", flush=True)

    print(f"distinct policy artifacts: {len(digests)}", flush=True)
    art_results = []
    for dg in sorted(digests):
        code, blob = http_get(TRANS + dg)
        time.sleep(0.15)
        r = {"digest": dg, "http": code, "keys": sorted(digests[dg]["keys"])}
        if code == 200:
            r["size"] = len(blob)
            r["hash_ok"] = hashlib.sha256(blob).hexdigest() == dg
            hits, magics = scan_blob(blob)
            r["marker_hits_whole"] = hits
            r["magic_whole"] = magics
            inv = walk(blob)
            len_fields = [(p, v) for p, v in inv if v is not None]
            r["fields_total"] = len(inv)
            r["len_fields"] = len(len_fields)
            r["max_depth"] = max((len(p) for p, _ in inv), default=0)
            fhits, fmagics, b64hits = {}, set(), {}
            big_opaque = []
            for p, v in len_fields:
                h2, m2 = scan_blob(v)
                for k, c in h2.items():
                    fhits[".".join(map(str, p)) + ":" + k] = c
                fmagics.update(m2)
                # long base64-looking printable fields: decode + rescan
                if len(v) >= 64 and printable_ratio(v) > 0.98:
                    for run in B64RUN.findall(v):
                        try:
                            dec = base64.b64decode(run, validate=False)
                        except Exception:
                            continue
                        h3, _ = scan_blob(dec)
                        if h3:
                            b64hits[".".join(map(str, p))] = h3
                if len(v) >= 1024 and printable_ratio(v) < 0.5:
                    big_opaque.append((len(v), round(entropy(v), 2),
                                       ".".join(map(str, p))))
            r["marker_hits_fields"] = fhits
            r["magic_fields"] = sorted(fmagics)
            r["b64_rescan_hits"] = b64hits
            r["big_opaque_fields"] = sorted(big_opaque, reverse=True)[:5]
        art_results.append(r)
        print(f"artifact {dg[:12]}: size={r.get('size')} fields={r.get('fields_total')} "
              f"whole={r.get('marker_hits_whole')} b64={r.get('b64_rescan_hits')}", flush=True)

    summary = {"payload_stats": payload_stats,
               "distinct_artifacts": len(digests),
               "artifacts": art_results}
    with open("battery/panel-2026-11-04/e10_wire_decode.json", "w") as f:
        json.dump(summary, f, indent=1)
    tot_markers = sum(sum(a.get("marker_hits_whole", {}).values())
                      for a in art_results)
    print(f"TOTAL whole-buffer marker hits across artifacts: {tot_markers}")
    print("done")

if __name__ == "__main__":
    main()
