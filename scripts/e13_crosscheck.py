#!/usr/bin/env python3
"""E13 — index cross-check + sampled chain authentication (2026-11-04).

For four endorsement keys (incl. the largest), take the index endpoint's
returned UUID list, draw a seeded sample, and for each sampled entry verify
via the INDEPENDENT log-entries route: leaf hash, RFC 6962 inclusion-proof
fold against the served checkpoint root, checkpoint note signature, and
Signed Entry Timestamp (method: records/E8-census-signatures.md Exp. B;
openssl CLI for ECDSA, sorted-keys canonical JSON for the SET).
"""
import base64, hashlib, json, random, re, subprocess, sys, time, urllib.request

API = "https://rekor.sigstore.dev/api/v1"
LOGID = "c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d"
PUBKEY = "/home/hatch/workspace/gap-papers/s3-sealed-audit/logs/rekor_pubkey.pem"
REPO = "/home/hatch/workspace/gap-papers/s3-sealed-audit/code/cfc-repo"
TARGETS = {  # fingerprint prefix -> label
    "2bb537ad": "Private Compute Services policy (largest key)",
    "5aac231c": "Recorder policy",
    "3ebd2cd4": "Gboard policy key 1",
    "ea0d1f8f": "application key (exemplar's key)",
}
SEED = 20261104
PER_KEY = 6

def http(req):
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def get_json(url):
    return json.loads(http(urllib.request.Request(url, headers={"Accept": "application/json"})))

def post_json(url, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    return json.loads(http(req))

def extract_keys():
    import glob
    files = glob.glob(REPO + "/kms/reference_values/*.txtpb") + glob.glob(REPO + "/access_policy_reference_values/*.txtpb")
    keys = {}
    for f in files:
        text = open(f).read()
        for m in re.finditer(r'raw:\s*"((?:\\x[0-9a-fA-F]{2}|[^"\\])*)"', text):
            s = m.group(1)
            der = bytes(int(s[i+2:i+4], 16) for i in range(0, len(s) - 3, 4) if s[i] == "\\" and s[i+1] == "x") if "\\x" in s else s.encode()
            fp = hashlib.sha256(der).hexdigest()
            keys[fp] = der
    return keys

def pem_of(der):
    b = base64.b64encode(der).decode()
    lines = [b[i:i+64] for i in range(0, len(b), 64)]
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n"

def openssl_verify(sig_der, data_bytes, pubkey_pem_text=None):
    with open("/tmp/e13_sig.der", "wb") as f: f.write(sig_der)
    with open("/tmp/e13_data.bin", "wb") as f: f.write(data_bytes)
    pub = PUBKEY
    if pubkey_pem_text:
        pub = "/tmp/e13_pub.pem"
        open(pub, "w").write(pubkey_pem_text)
    out = subprocess.run(["openssl", "dgst", "-sha256", "-verify", pub, "-signature", "/tmp/e13_sig.der", "/tmp/e13_data.bin"],
                         capture_output=True, text=True)
    return "Verified OK" in out.stdout

def fold_proof(leaf, index, tree_size, hashes):
    fn, sn = index, tree_size - 1
    r = leaf
    for h in hashes:
        hb = bytes.fromhex(h)
        if sn == 0:
            return None
        if fn % 2 == 1 or fn == sn:
            r = hashlib.sha256(b"\x01" + hb + r).digest()
            while fn % 2 == 0 and fn != 0:
                fn //= 2; sn //= 2
        else:
            r = hashlib.sha256(b"\x01" + r + hb).digest()
        fn //= 2; sn //= 2
    return r

def main():
    keys = extract_keys()
    print(f"extracted {len(keys)} unique keys", file=sys.stderr)
    rng = random.Random(SEED)
    results = []
    for prefix, label in TARGETS.items():
        fp = next((k for k in keys if k.startswith(prefix)), None)
        assert fp, f"key {prefix} not found"
        pem = pem_of(keys[fp])
        uuids = post_json(API + "/index/retrieve", {"publicKey": {"format": "x509", "content": base64.b64encode(pem.encode()).decode()}})
        sample = rng.sample(uuids, min(PER_KEY, len(uuids)))
        print(f"{label}: index returned {len(uuids)}; sampled {len(sample)}", file=sys.stderr)
        for uuid in sample:
            e = get_json(API + f"/log/entries/{uuid}")[uuid]
            body_b64 = e["body"]
            body = base64.b64decode(body_b64)
            proof = e["verification"]["inclusionProof"]
            leaf = hashlib.sha256(b"\x00" + body).digest()
            folded = fold_proof(leaf, proof["logIndex"], proof["treeSize"], proof["hashes"])
            fold_ok = folded is not None and folded.hex() == proof["rootHash"]
            # checkpoint note signature
            ckpt = proof["checkpoint"]
            lines = ckpt.split("\n")
            note_text = "\n".join(lines[:3]) + "\n"
            sig_line = next(l for l in lines if l.startswith("— "))
            sig_raw = base64.b64decode(sig_line.split(" ", 2)[2])
            ckpt_ok = openssl_verify(sig_raw[4:], note_text.encode())
            ckpt_root = base64.b64decode(lines[2]).hex()
            ckpt_consistent = ckpt_root == proof["rootHash"] and int(lines[1]) == proof["treeSize"]
            # SET
            canon = json.dumps({"body": body_b64, "integratedTime": e["integratedTime"],
                                "logID": LOGID, "logIndex": e["logIndex"]},
                               sort_keys=True, separators=(",", ":"))
            set_ok = openssl_verify(base64.b64decode(e["verification"]["signedEntryTimestamp"]), canon.encode())
            results.append({"key": prefix, "label": label, "uuid": uuid,
                            "logIndex": e["logIndex"], "proofIndex": proof["logIndex"],
                            "fold_ok": fold_ok, "checkpoint_sig_ok": ckpt_ok,
                            "checkpoint_consistent": ckpt_consistent, "set_ok": set_ok})
            print(f"  {uuid[:12]} fold={fold_ok} ckpt={ckpt_ok} consist={ckpt_consistent} set={set_ok}", file=sys.stderr)
            time.sleep(0.3)
    json.dump(results, open("/tmp/e13_out.json", "w"), indent=1)
    n = len(results)
    print(f"TOTAL {n}: fold {sum(r['fold_ok'] for r in results)}/{n}, "
          f"ckpt-sig {sum(r['checkpoint_sig_ok'] for r in results)}/{n}, "
          f"ckpt-consistent {sum(r['checkpoint_consistent'] for r in results)}/{n}, "
          f"SET {sum(r['set_ok'] for r in results)}/{n}")

if __name__ == "__main__":
    main()
