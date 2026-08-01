"""End to end: launch tx -> factsheet -> judge -> verdict card PNG.

Usage:
    python3 scripts/card_run.py [tx_hash] [--stub] [--out path.png]

--stub uses the offline judge stand-in (no API key needed).
Defaults to the HOTDOG/COST fixture launch.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.judge import judge_factsheet  # noqa: E402
from card.render import render_card  # noqa: E402
from gavel.chain import Rpc  # noqa: E402
from gavel.checks import build_factsheet  # noqa: E402
from gavel.constants import LBP_STRATEGY, ZERO_ADDRESS  # noqa: E402
from gavel.decode import find_launch_logs  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                       "hotdog_launch_receipt.json")
MARK = os.path.join(os.path.dirname(__file__), "..", "brand",
                    "gavel-mark-tight.png")


def stub_model(system_prompt, user_prompt):
    import re
    ceiling = re.search(r'"verdict_ceiling":\s*"(\w+)"', user_prompt).group(1)
    keys = re.findall(r'"check":\s*"([^"]+)"', user_prompt)
    return {
        "verdict": ceiling,
        "key_findings": keys[:8],
        "hook_assessment": "unknown",
        "currency_assessment": "unknown",
        "recipient_assessment": "unknown",
        "manipulation_detected": False,
    }


def main():
    argv = sys.argv[1:]
    out = "data/cards/card.png"
    if "--out" in argv:
        i = argv.index("--out")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    rpc = Rpc()
    if args:
        receipt = rpc.call("eth_getTransactionReceipt", [args[0]])
    else:
        with open(FIXTURE) as f:
            receipt = json.load(f)

    launches = find_launch_logs(receipt, LBP_STRATEGY)
    if not launches:
        print("no launches in this receipt")
        return

    model = stub_model if "--stub" in sys.argv else None
    for i, launch in enumerate(launches):
        sheet = build_factsheet(rpc, launch)
        verdict = judge_factsheet(sheet, model=model)
        p = launch["params"]
        token_symbol = rpc.read_string(p["token"], Rpc.SEL_SYMBOL)
        currency_symbol = (
            "ETH" if p["currency"] == ZERO_ADDRESS
            else rpc.read_string(p["currency"], Rpc.SEL_SYMBOL)
        )
        path = out if len(launches) == 1 else out.replace(".png", "-%d.png" % i)
        render_card(verdict, sheet, token_symbol, currency_symbol, path,
                    mark_path=MARK)
        print("VERDICT %-4s -> %s" % (verdict["verdict"], path))


if __name__ == "__main__":
    main()
