"""Write the static JSON API from the built feed and deployer index.

The site publishes the same data it renders. Keeping this as its own step
means a refresh is three commands rather than a remembered incantation.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUT = os.path.join("site", "public", "v1")


def public(r):
    return {
        "auction": r["ini"],
        "tx": r["tx"],
        "block": r["block"],
        "token": {"address": r["token"], "symbol": r["sym"]},
        "currency": {
            "address": r["currency"],
            "symbol": r["cur_sym"],
            "official_stock_token": r["cur_official"],
        },
        "recipient": {
            "address": r["recipient"],
            "is_contract": r["rec_code"] > 0,
            "nonce": r["rec_nonce"],
        },
        "lp_reserve_ratio": r["lp_ratio"],
        "pool": {"fee": r["fee"], "hook": r["hook"]},
        "migration_block": r["migration_block"],
        "outcome": r["state"],
        "ceiling": r["ceiling"],
        "findings": [
            {"check": f["k"], "severity": f["s"], "detail": f["d"]}
            for f in r["findings"]
        ],
    }


def main():
    feed = json.load(open("data/feed.json"))
    deployers = json.load(open("data/deployers.json"))
    rows, head = feed["rows"], feed["head"]

    os.makedirs(os.path.join(OUT, "launch"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "deployer"), exist_ok=True)

    def dump(name, obj):
        with open(os.path.join(OUT, name), "w") as f:
            json.dump(obj, f, separators=(",", ":"))

    live = [public(r) for r in rows if r["state"] == "live"]
    dump("live.json", {"head": head, "count": len(live), "launches": live})
    dump("launches.json", {"head": head, "count": len(rows),
                           "launches": [public(r) for r in rows]})
    for r in rows:
        dump(os.path.join("launch", r["ini"].lower() + ".json"), public(r))
    for d in deployers["deployers"]:
        dump(os.path.join("deployer", d["addr"].lower() + ".json"), d)
    dump("deployers.json", deployers)
    print("wrote %d launches, %d deployers at head %d"
          % (len(rows), len(deployers["deployers"]), head))


if __name__ == "__main__":
    main()
