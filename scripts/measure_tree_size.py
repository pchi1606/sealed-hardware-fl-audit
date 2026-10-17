#!/usr/bin/env python3
"""Measure Rekor's tree size by binary-searching the index-retrieval endpoint.

Author: Prabhu Rangaraju

Method (as described in the manuscript, S4.4): POST
/api/v1/log/entries/retrieve with {"logIndexes": [N]} returns the entry
when N is a valid index and an empty result when N exceeds the tree size.
Binary search finds the largest valid index; tree size = that index + 1.

Sequential requests only, no parallelism (rate-limit courtesy).
Saves the raw transcript to logs/treesize_<date>.json.
"""

import json
import time
import urllib.request
from datetime import datetime, timezone

REKOR = "https://rekor.sigstore.dev/api/v1"


def has_index(n, tries=3):
    """Return True if log index n exists (any of `tries` attempts).

    The endpoint flaps (see manuscript S4.4): a single empty result is not
    conclusive, so we require `tries` consecutive empty results to call an
    index absent.
    """
    for _ in range(tries):
        req = urllib.request.Request(
            REKOR + "/log/entries/retrieve",
            data=json.dumps({"logIndexes": [n]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
                if body:
                    return True
        except Exception as e:  # noqa: BLE001 - endpoint flaps; retry
            print(f"  index {n}: {type(e).__name__} (retrying)")
        time.sleep(2)
    return False


def main():
    transcript = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "method": "binary search over POST /api/v1/log/entries/retrieve logIndexes",
        "probes": [],
    }
    # Exponential probe for an upper bound, then binary search.
    lo, hi = 0, 1
    while has_index(hi):
        lo = hi
        hi *= 2
        transcript["probes"].append({"hi_probe": hi, "exists": True})
        time.sleep(1)
    transcript["probes"].append({"hi_probe": hi, "exists": False})
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if has_index(mid):
            lo = mid
        else:
            hi = mid
        time.sleep(1)
    transcript["max_index"] = lo
    transcript["tree_size"] = lo + 1
    print(f"max index: {lo}, tree size: {lo + 1}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = f"logs/treesize_{stamp}.json"
    with open(out, "w") as f:
        json.dump(transcript, f, indent=2)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
