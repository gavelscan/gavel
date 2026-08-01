"""Write the homepage dataset: one row per launch, plus the archive totals.

The hero legend and the figures beside it were assembled by hand once and
then never moved, so the page kept asserting a count the chain had long
since passed. Everything the homepage states now comes from here, and
here comes from the archive.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gavel.constants import ZERO_ADDRESS  # noqa: E402

ARCHIVE = "data/events.jsonl"
OUT = "site/src/app/launches.json"


def main():
    feed = json.load(open("data/feed.json"))
    rows = feed["rows"]

    events = sum(1 for line in open(ARCHIVE) if line.strip())

    launches = [
        {
            "b": r["block"],
            "s": r["state"],
            "c": 0 if r["currency"] == ZERO_ADDRESS else 1,
            "lp": round(r["lp_ratio"] or 0, 4),
        }
        for r in sorted(rows, key=lambda x: x["block"])
    ]

    with open(OUT, "w") as f:
        json.dump({"head": feed["head"], "events": events,
                   "launches": launches}, f, separators=(",", ":"))
    print("wrote %s: %d launches, %d archived events"
          % (OUT, len(launches), events))


if __name__ == "__main__":
    main()
