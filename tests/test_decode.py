"""Decoder tests against a real mainnet fixture.

Fixture: the HOTDOG launch — the first stock-paired launch we found on
Robinhood Chain. tx 0x785de68766c44b1945f431b969f5df7d8de2f2e7e01b709f43dc10276b49801f
(block 23898781). Token HOTDOG auctioned against COST (Costco stock token).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gavel.constants import LBP_STRATEGY, ZERO_ADDRESS  # noqa: E402
from gavel.decode import (  # noqa: E402
    DecodeError,
    decode_initializer_created,
    decode_token_created,
    find_launch_logs,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hotdog_launch_receipt.json")

HOTDOG = "0xb89d67d60f94c9b3bef6d108e0be57fd90017e2f"
COST = "0x4ea005168d7f09a7a0ba9d1def21a479950e44c2"
HOTDOG_INITIALIZER = "0x152d95fd87874771584e019aabf2292d1860a3f3"


def load_receipt():
    with open(FIXTURE) as f:
        return json.load(f)


class TestDecodeHotdogLaunch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = load_receipt()
        cls.launches = find_launch_logs(cls.receipt, LBP_STRATEGY)

    def test_exactly_one_launch_in_receipt(self):
        self.assertEqual(len(self.launches), 1)

    def test_initializer_address(self):
        self.assertEqual(self.launches[0]["initializer"].lower(), HOTDOG_INITIALIZER)

    def test_token_is_hotdog(self):
        self.assertEqual(self.launches[0]["params"]["token"].lower(), HOTDOG)

    def test_currency_is_cost_stock_token(self):
        self.assertEqual(self.launches[0]["params"]["currency"].lower(), COST)

    def test_currency_is_not_native(self):
        self.assertNotEqual(self.launches[0]["params"]["currency"], ZERO_ADDRESS)

    def test_reserved_lp_positive(self):
        self.assertGreater(self.launches[0]["params"]["reservedTokenAmountForLP"], 0)

    def test_recipient_nonzero(self):
        self.assertNotEqual(self.launches[0]["params"]["recipient"], ZERO_ADDRESS)

    def test_position_recipient_nonzero(self):
        self.assertNotEqual(self.launches[0]["params"]["positionRecipient"], ZERO_ADDRESS)

    def test_migration_block_after_launch_block(self):
        launch = self.launches[0]
        self.assertGreater(launch["params"]["migrationBlock"], launch["block"])

    def test_schedule_decodes_and_is_wellformed(self):
        sched = self.launches[0]["params"]["lpAllocationSchedule"]
        self.assertGreaterEqual(len(sched), 1)
        self.assertEqual(sched[0]["lowerThreshold"], 0)
        for b in sched:
            self.assertGreater(b["rate"], 0)
            self.assertLessEqual(b["rate"], 10_000_000)

    def test_pool_fields_present(self):
        pool = self.launches[0]["params"]["pool"]
        self.assertIn("fee", pool)
        self.assertIn("tickSpacing", pool)
        self.assertIn("hook", pool)
        self.assertNotEqual(pool["tickSpacing"], 0)

    def test_tx_hash_recorded(self):
        self.assertTrue(self.launches[0]["tx"].startswith("0x"))


class TestDecodeRejectsWrongLogs(unittest.TestCase):
    def test_token_created_rejects_other_topic(self):
        log = {"topics": ["0x" + "ab" * 32, "0x" + "00" * 32], "blockNumber": "0x1",
               "transactionHash": "0x0", "data": "0x"}
        with self.assertRaises(DecodeError):
            decode_token_created(log)

    def test_initializer_created_rejects_other_topic(self):
        log = {"topics": ["0x" + "ab" * 32, "0x" + "00" * 32], "blockNumber": "0x1",
               "transactionHash": "0x0", "data": "0x"}
        with self.assertRaises(DecodeError):
            decode_initializer_created(log)

    def test_find_launch_logs_ignores_other_contracts(self):
        receipt = load_receipt()
        self.assertEqual(find_launch_logs(receipt, "0x" + "11" * 20), [])


if __name__ == "__main__":
    unittest.main()


class TestLifecycleEventDecoders(unittest.TestCase):
    """The four lifecycle events the topic-filtered v1 watcher missed."""

    def _log(self, topic0, indexed, amount):
        return {
            "address": LBP_STRATEGY,
            "topics": [topic0] + ["0x" + "00" * 12 + a for a in indexed],
            "data": "0x" + "%064x" % amount,
            "blockNumber": "0x64",
            "transactionHash": "0x" + "cd" * 32,
        }

    def test_token_distributed(self):
        from gavel.constants import TOPIC_TOKEN_DISTRIBUTED
        from gavel.decode import decode_any
        rec = decode_any(self._log(TOPIC_TOKEN_DISTRIBUTED,
                                   ["11" * 20, "22" * 20], 1000))
        self.assertEqual(rec["event"], "TokenDistributed")
        self.assertEqual(rec["token"], "0x" + "11" * 20)
        self.assertEqual(rec["strategy"], "0x" + "22" * 20)
        self.assertEqual(rec["amount"], 1000)

    def test_currency_swept(self):
        from gavel.constants import TOPIC_CURRENCY_SWEPT
        from gavel.decode import decode_any
        rec = decode_any(self._log(TOPIC_CURRENCY_SWEPT, ["33" * 20], 7))
        self.assertEqual(rec["event"], "CurrencySwept")
        self.assertEqual(rec["recipient"], "0x" + "33" * 20)

    def test_tokens_swept(self):
        from gavel.constants import TOPIC_TOKENS_SWEPT
        from gavel.decode import decode_any
        rec = decode_any(self._log(TOPIC_TOKENS_SWEPT, ["44" * 20], 9))
        self.assertEqual(rec["event"], "TokensSwept")
        self.assertEqual(rec["amount"], 9)

    def test_funds_recovered(self):
        from gavel.constants import TOPIC_FUNDS_RECOVERED
        from gavel.decode import decode_any
        rec = decode_any(self._log(TOPIC_FUNDS_RECOVERED,
                                   ["55" * 20, "66" * 20], 12))
        self.assertEqual(rec["event"], "FundsRecovered")
        self.assertEqual(rec["initializer"], "0x" + "55" * 20)
        self.assertEqual(rec["recipient"], "0x" + "66" * 20)

    def test_malformed_indexed_amount_becomes_decode_failed(self):
        from gavel.constants import TOPIC_FUNDS_RECOVERED
        from gavel.decode import decode_any
        log = self._log(TOPIC_FUNDS_RECOVERED, ["55" * 20], 12)  # missing topic
        rec = decode_any(log)
        self.assertEqual(rec["event"], "DecodeFailed")
