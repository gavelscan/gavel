"""Build the deployer index from the feed.

One row per address that has created a launch auction, with what became
of the launches it created. This is the honest form of "is the deployer
trustworthy": not a judgement, a record.
"""

import collections
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    feed = json.load(open("data/feed.json"))
    rows, head = feed["rows"], feed["head"]

    by = collections.defaultdict(list)
    for r in rows:
        by[r["recipient"].lower()].append(r)

    deployers = []
    for rs in by.values():
        lps = [r["lp_ratio"] for r in rs if r["lp_ratio"] is not None]
        deployers.append({
            "addr": rs[0]["recipient"],
            "n": len(rs),
            "pool": sum(1 for r in rs if r["state"] == "pool"),
            "failed": sum(1 for r in rs if r["state"] == "failed"),
            "live": sum(1 for r in rs if r["state"] == "live"),
            "silent": sum(1 for r in rs if r["state"] == "silent"),
            "median_lp": sorted(lps)[len(lps) // 2] if lps else None,
            "is_contract": rs[0]["rec_code"] > 0,
            "first_block": min(r["block"] for r in rs),
            "last_block": max(r["block"] for r in rs),
            "tokens": [
                {"sym": r["sym"], "ini": r["ini"], "state": r["state"],
                 "ceiling": r["ceiling"]}
                for r in sorted(rs, key=lambda x: -x["block"])[:12]
            ],
        })
    deployers.sort(key=lambda d: (-d["n"], -d["last_block"]))
    with open("data/deployers.json", "w") as f:
        json.dump({"head": head, "deployers": deployers}, f, separators=(",", ":"))
    print("wrote data/deployers.json: %d deployers" % len(deployers))


if __name__ == "__main__":
    main()
