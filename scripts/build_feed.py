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
from gavel.lock import Locked, exclusive  # noqa: E402
from gavel.checks import CHECKS_VERSION, build_factsheet  # noqa: E402
from gavel.constants import ZERO_ADDRESS  # noqa: E402

ARCHIVE = "data/events.jsonl"
CACHE = "data/feed-cache.json"
LOCK = "data/.feed-cache.lock"
OUT = "data/feed.json"


def load_cache():
    """Prefer the working cache; fall back to the last published feed.

    Rebuilding from an empty cache means every launch depends on the node
    answering right now, and a flaky node then drops launches from the
    record entirely — the count on the site would quietly shrink. Seeding
    from the published feed makes a refresh additive.
    """
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    seed = {}
    for path in (OUT, os.path.join("site", "src", "app", "feed.json")):
        if os.path.exists(path):
            with open(path) as f:
                for row in json.load(f).get("rows", []):
                    seed[row["ini"].lower()] = row
            break
    if seed:
        print("seeded cache with %d rows from the last published feed" % len(seed))
    return seed


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
    unresolved = []
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
            state = "silent"  # refined below once the auction is read

        if ini in cache and cache[ini].get("v") == CHECKS_VERSION:
            row = cache[ini]
            row["state"] = state  # state can change over time
            if "cleared" not in row:
                try:
                    o = rpc.auction_outcome(launch["initializer"])
                    row.update(cleared=o["cleared"], sold=o["sold"],
                               raised=o["raised"])
                    cache[ini] = row
                except RpcError:
                    unresolved.append(ini)
            # An auction past its migration block that never reached a
            # clearing price did not "fail to migrate" — nobody bid enough
            # for there to be anything to migrate. Say which.
            if state == "silent" and row.get("cleared") is False:
                row["state"] = "unfilled"
        else:
            try:
                outcome = rpc.auction_outcome(launch["initializer"])
                launch["sold"] = outcome["sold"]
                launch["migrated"] = ini in migrated
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
                    "cleared": outcome["cleared"],
                    "sold": outcome["sold"],
                    "raised": outcome["raised"],
                    "ceiling": sheet["ceiling"],
                    "findings": [
                        {"k": k, "s": s, "d": d} for k, s, d in sheet["findings"]
                    ],
                    "state": ("unfilled" if state == "silent"
                              and not outcome["cleared"] else state),
                    "v": CHECKS_VERSION,
                }
                cache[ini] = row
                if i % 10 == 0:
                    save_cache(cache)
                    print("  %d/%d" % (i + 1, len(todo)), flush=True)
            except RpcError as e:
                # Unreachable is not absent (I5). Keep whatever we already
                # published for this launch rather than deleting it from
                # the record; if we have nothing, leave it out of this
                # build and say so, but never write a guess.
                print("  unresolved %s: %s" % (ini[:10], str(e)[:70]), flush=True)
                unresolved.append(launch)
                continue
            time.sleep(0.05)
        rows.append(row)

    # A transient node failure must not quietly shrink the record, so every
    # deferred launch gets one more attempt before the build is written.
    still_absent = []
    if unresolved:
        print("retrying %d deferred launch(es)" % len(unresolved), flush=True)
        for launch in unresolved:
            ini = launch["initializer"].lower()
            p2 = launch["params"]
            try:
                outcome = rpc.auction_outcome(launch["initializer"])
                launch["sold"] = outcome["sold"]
                launch["migrated"] = ini in migrated
                sheet = build_factsheet(rpc, launch, current_block=head)
            except RpcError:
                still_absent.append(ini)
                continue
            base = "live" if p2["migrationBlock"] >= head else "silent"
            cache[ini] = {
                "ini": launch["initializer"], "tx": launch["tx"],
                "block": launch["block"], "token": p2["token"],
                "sym": rpc.read_string(p2["token"], Rpc.SEL_SYMBOL),
                "currency": p2["currency"],
                "cur_sym": ("ETH" if p2["currency"] == ZERO_ADDRESS
                            else rpc.read_string(p2["currency"], Rpc.SEL_SYMBOL)),
                "cur_official": bool(sheet["currency"].get("official")),
                "recipient": p2["recipient"],
                "rec_code": sheet["recipient"]["code_size"],
                "rec_nonce": sheet["recipient"]["nonce"],
                "lp_ratio": sheet["reserved_lp_ratio"],
                "fee": p2["pool"]["fee"], "hook": p2["pool"]["hook"],
                "migration_block": p2["migrationBlock"],
                "cleared": outcome["cleared"], "sold": outcome["sold"],
                "raised": outcome["raised"], "ceiling": sheet["ceiling"],
                "findings": [{"k": k, "s": sv, "d": d}
                             for k, sv, d in sheet["findings"]],
                "state": ("unfilled" if base == "silent"
                          and not outcome["cleared"] else base),
                "v": CHECKS_VERSION,
            }
            rows.append(cache[ini])

    save_cache(cache)
    rows.sort(key=lambda r: -r["block"])
    with open(OUT, "w") as f:
        json.dump({"head": head, "rows": rows}, f, separators=(",", ":"))
    print("wrote %s: %d rows" % (OUT, len(rows)))
    if still_absent:
        # Loud, because a launch missing from the record is the one failure
        # this project cannot afford to shrug at.
        print("WARNING: %d launch(es) unreadable after a retry and absent "
              "from this build; they will be attempted again next run: %s"
              % (len(still_absent), ", ".join(a[:10] for a in still_absent[:5])),
              flush=True)


if __name__ == "__main__":
    # Held for the whole build: the cache is written at the end, but it is
    # read at the start, so overlapping runs corrupt each other even when
    # only one of them writes.
    try:
        with exclusive(LOCK, "the feed cache"):
            main()
    except Locked as e:
        sys.exit("build_feed: %s" % e)
