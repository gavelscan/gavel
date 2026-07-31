"""Dry run: build a deterministic factsheet for one real launch.

Usage: python3 scripts/dry_run.py [tx_hash]
Defaults to the HOTDOG/COST fixture receipt (offline decode, live facts).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gavel.chain import Rpc  # noqa: E402
from gavel.checks import build_factsheet  # noqa: E402
from gavel.constants import LBP_STRATEGY  # noqa: E402
from gavel.decode import find_launch_logs  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                       "hotdog_launch_receipt.json")


def main():
    rpc = Rpc()
    if len(sys.argv) > 1:
        receipt = rpc.call("eth_getTransactionReceipt", [sys.argv[1]])
    else:
        with open(FIXTURE) as f:
            receipt = json.load(f)

    launches = find_launch_logs(receipt, LBP_STRATEGY)
    if not launches:
        print("no InitializerCreated logs from LBPStrategy in this receipt")
        return

    for launch in launches:
        sheet = build_factsheet(rpc, launch)
        p = launch["params"]
        print("=" * 60)
        print("launch tx    :", launch["tx"])
        print("initializer  :", launch["initializer"])
        print("token        :", p["token"])
        print("currency     :", sheet["currency"].get("symbol"), "|",
              sheet["currency"].get("name"), "(%s)" % sheet["currency"]["kind"])
        print("recipient    :", p["recipient"],
              "| code_size=%d nonce=%d" % (sheet["recipient"]["code_size"],
                                           sheet["recipient"]["nonce"]))
        print("pool         : fee=%d tickSpacing=%d hook=%s" % (
            p["pool"]["fee"], p["pool"]["tickSpacing"], p["pool"]["hook"]))
        print("schedule     :", p["lpAllocationSchedule"])
        print("positions    :", len(p["positionDefinitions"]), "explicit definitions")
        if sheet["reserved_lp_ratio"] is not None:
            print("LP reserve   : %.2f%% of supply" % (sheet["reserved_lp_ratio"] * 100))
        print("migration in :", sheet["blocks_until_migration"], "blocks")
        print("-" * 60)
        for name, sev, detail in sheet["findings"]:
            print("[%s] %-28s %s" % (sev, name, detail))
        print("-" * 60)
        print("VERDICT CEILING:", sheet["ceiling"],
              "(judge may lower, never raise)")


if __name__ == "__main__":
    main()
