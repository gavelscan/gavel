"""Render the posting deck, refusing to publish a number the record does
not support.

Every figure that appears in card copy is declared in content/cards.json
as a check against the live feed. A card whose number has gone stale does
not quietly render with the old figure — the build stops and names it.

That guard is the entire reason this is a script instead of a design
file. The record moves every fifteen minutes; a deck drawn by hand is
correct on the day it is drawn and slowly becomes a lie.

Usage:
    python3 scripts/cards_build.py              # render all, verify first
    python3 scripts/cards_build.py record live  # render named slugs only
    python3 scripts/cards_build.py --posts      # print the post copy
"""

import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from card.statement import (  # noqa: E402
    CopyTooLong, render_banner, render_statement,
)

DECK = "content/cards.json"
ARTICLES = "content/articles.json"
FEED = "data/feed.json"
OUT_DIR = "data/cards/deck"
ART_DIR = "data/cards/articles"


def facts():
    """The figures a card is allowed to quote, derived from the feed."""
    rows = json.load(open(FEED))["rows"]
    by_state = {}
    for r in rows:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    f = {
        "total": len(rows),
        "pool": by_state.get("pool", 0),
        "unfilled": by_state.get("unfilled", 0),
        "live": by_state.get("live", 0),
        "failed": by_state.get("failed", 0),
        "deployers": len({r["recipient"].lower() for r in rows}),
    }
    if os.path.exists("data/events.jsonl"):
        f["events"] = sum(1 for line in open("data/events.jsonl") if line.strip())
    return f


def verify(items, f):
    """Returns a list of human-readable problems; empty means publishable."""
    problems = []
    for card in items:
        for key, expected in card.get("checks", []):
            if key not in f:
                problems.append("%s: unknown figure %r" % (card["slug"], key))
                continue
            if f[key] != expected:
                problems.append(
                    "%s: copy says %s = %s, the record says %s"
                    % (card["slug"], key, expected, f[key]))
    return problems


def build_articles(args, f):
    """Render article banners and print the bodies.

    The banner carries no figures, but the body does, so the same refusal
    applies: an article whose numbers have drifted does not get a header
    image encouraging someone to publish it.
    """
    doc = json.load(open(ARTICLES))
    problems = verify(doc["articles"], f)
    if problems:
        print("REFUSING — the record has moved under these articles:")
        for p in problems:
            print("  " + p)
        return 1
    os.makedirs(ART_DIR, exist_ok=True)
    for a in doc["articles"]:
        if args and a["slug"] not in args:
            continue
        out = os.path.join(ART_DIR, a["slug"] + ".png")
        try:
            render_banner(a["banner_headline"], a["banner_accent"], out)
        except CopyTooLong as e:
            print("%s: %s" % (a["slug"], e))
            return 1
        print("wrote %s  (5:2)" % out)
        body = os.path.join(ART_DIR, a["slug"] + ".md")
        with open(body, "w") as fh:
            fh.write("# %s\n\n*%s*\n\n%s\n" % (a["title"], a["subtitle"], a["body"]))
        words = len(a["body"].split())
        print("wrote %s  (%d words, ~%d min read)" % (body, words, max(1, round(words / 220))))
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    f = facts()

    if "--articles" in sys.argv:
        return build_articles(args, f)

    deck = json.load(open(DECK))
    problems = verify(deck["cards"], f)
    if problems:
        print("REFUSING TO RENDER — the record has moved under this deck:")
        for p in problems:
            print("  " + p)
        print("\nCurrent figures: " + ", ".join("%s=%s" % kv for kv in sorted(f.items())))
        print("Update content/cards.json (copy AND checks), then run again.")
        return 1

    if "--posts" in sys.argv:
        for card in deck["cards"]:
            if args and card["slug"] not in args:
                continue
            print("=" * 66)
            print("%s   [card: %s.png]" % (card["slug"].upper(), card["slug"]))
            print("=" * 66)
            for para in card["post"].split("\n"):
                print(textwrap.fill(para, 66) if para else "")
            n = len(card["post"])
            print("\n(%d chars%s)\n" % (n, "" if n <= 280 else " — over 280, needs a thread or Premium"))
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    too_long = 0
    for card in deck["cards"]:
        if args and card["slug"] not in args:
            continue
        out = os.path.join(OUT_DIR, card["slug"] + ".png")
        try:
            render_statement(card["headline"], card["accent"],
                             card.get("subline", ""), out)
        except CopyTooLong as e:
            print("%s: %s" % (card["slug"], e))
            too_long += 1
            continue
        print("wrote %s" % out)
    print("\nverified against the record at %d launches" % f["total"])
    if too_long:
        print("%d card(s) not rendered — copy too long" % too_long)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
