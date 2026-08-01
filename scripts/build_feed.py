"""Build the site feed dataset: every launch with its deterministic facts.

One row per launch auction, carrying the identifiers a reader needs and
the deterministic verdict ceiling. The ceiling is computed without the
model, so this whole file is reproducible from chain state alone — the
judge's classification is layered on separately for launches that have
been judged.

Resumable: results are cached per initializer, so a broken run picks up
where it stopped instead of re-reading the chain from the top.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gavel.chain import Rpc, RpcError  # noqa: E402
from gavel.checks import build_factsheet  # noqa: E402
from gavel.constants import ZERO_ADDRESS  # noqa: E402

ARCHIVE = "data/events.jsonl"
CACHE = "data/feed-cache.json"
OUT = "data/feed.json"


def load_cache():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    events = [json.loads(l) for l in open(ARCHIVE)]
    launches = [e for e in events if e["event"] == "InitializerCreated"]
    migrated = {e["initializer"].lower() for e in events if e["event"] == "Migrated"}
    failed = {e["initializer"].lower() for e in events if e["event"] == "MigrationFailed"}

    rpc = Rpc()
    head = rpc.block_number()
    cache = load_cache()
    rows = []
    todo = sorted(launches, key=lambda x: -x["block"])
    if limit:
        todo = todo[:limit]

    for i, launch in enumerate(todo):
        ini = launch["initializer"].lower()
        p = launch["params"]
        if ini in migrated:
            state = "pool"
        elif ini in failed:
            state = "failed"
        elif p["migrationBlock"] >= head:
            state = "live"
        else:
            state = "silent"

        if ini in cache:
            row = cache[ini]
            row["state"] = state  # state can change over time
        else:
            try:
                sheet = build_factsheet(rpc, launch, current_block=head)
                token_symbol = rpc.read_string(p["token"], Rpc.SEL_SYMBOL)
                currency_symbol = (
                    "ETH" if p["currency"] == ZERO_ADDRESS
                    else rpc.read_string(p["currency"], Rpc.SEL_SYMBOL)
                )
                row = {
                    "ini": launch["initializer"],
                    "tx": launch["tx"],
                    "block": launch["block"],
                    "token": p["token"],
                    "sym": token_symbol,
                    "currency": p["currency"],
                    "cur_sym": currency_symbol,
                    "cur_official": bool(sheet["currency"].get("official")),
                    "recipient": p["recipient"],
                    "rec_code": sheet["recipient"]["code_size"],
                    "rec_nonce": sheet["recipient"]["nonce"],
                    "lp_ratio": sheet["reserved_lp_ratio"],
                    "fee": p["pool"]["fee"],
                    "hook": p["pool"]["hook"],
                    "migration_block": p["migrationBlock"],
                    "ceiling": sheet["ceiling"],
                    "findings": [
                        {"k": k, "s": s, "d": d} for k, s, d in sheet["findings"]
                    ],
                    "state": state,
                }
                cache[ini] = row
                if i % 10 == 0:
                    save_cache(cache)
                    print("  %d/%d" % (i + 1, len(todo)), flush=True)
            except RpcError as e:
                print("  skip %s: %s" % (ini[:10], e), flush=True)
                continue
            time.sleep(0.05)
        rows.append(row)

    save_cache(cache)
    rows.sort(key=lambda r: -r["block"])
    with open(OUT, "w") as f:
        json.dump({"head": head, "rows": rows}, f, separators=(",", ":"))
    print("wrote %s: %d rows" % (OUT, len(rows)))


if __name__ == "__main__":
    main()
