"""Judge a launch end-to-end: build the factsheet, then run the judge.

Usage:
    python3 scripts/judge_run.py [tx_hash]         # real model (needs ANTHROPIC_API_KEY)
    python3 scripts/judge_run.py [tx_hash] --stub  # deterministic stub, no network

The stub echoes the deterministic ceiling as its verdict with fixed
prose — enough to exercise the full pipeline (schema, gates, clamp)
without an API key. Defaults to the HOTDOG/COST fixture.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.judge import judge_factsheet  # noqa: E402
from gavel.chain import Rpc  # noqa: E402
from gavel.checks import build_factsheet  # noqa: E402
from gavel.constants import LBP_STRATEGY  # noqa: E402
from gavel.decode import find_launch_logs  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                       "hotdog_launch_receipt.json")


def stub_model(system_prompt, user_prompt):
    """Offline stand-in: mirror the ceiling, echo real finding keys."""
    import re
    ceiling = re.search(r'"verdict_ceiling":\s*"(\w+)"', user_prompt).group(1)
    keys = re.findall(r'"check":\s*"([^"]+)"', user_prompt)
    return {
        "verdict": ceiling,
        "key_findings": keys[:8],
        "hook_assessment": "none",
        "currency_assessment": "plausible",
        "recipient_assessment": "unknown",
        "manipulation_detected": False,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_stub = "--stub" in sys.argv
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

    model = stub_model if use_stub else None
    for launch in launches:
        sheet = build_factsheet(rpc, launch)
        verdict = judge_factsheet(sheet, model=model)
        print("=" * 60)
        print("VERDICT:", verdict["verdict"],
              "(ceiling %s, model said %s%s)" % (
                  verdict["ceiling"], verdict["model_verdict"],
                  ", clamped" if verdict["clamped"] else ""))
        print("hook:      ", verdict["hook_assessment"])
        print("currency:  ", verdict["currency_assessment"])
        print("recipient: ", verdict["recipient_assessment"])
        print("findings:  ", verdict["key_findings"])
        if verdict["manipulation_detected"]:
            print("  ⚠ manipulation_detected", verdict["manipulation_deterministic"] or "")
        print("tx:", verdict["tx"])


if __name__ == "__main__":
    main()
