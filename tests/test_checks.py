"""Checks + verdict-ceiling tests. Pure, no network.

The most important tests in this file are the clamp tests: the agent can
NEVER raise a verdict above the deterministic ceiling (Invariant I3).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gavel.checks import (  # noqa: E402
    FAIL,
    FLAG,
    PASS,
    check_pool,
    check_positions,
    check_recipient,
    check_schedule,
    clamp_verdict,
    worse,
)
from gavel.constants import DYNAMIC_FEE_FLAG, MAX_TICK, MIN_TICK, ZERO_ADDRESS  # noqa: E402


def bracket(lower, rate):
    return {"lowerThreshold": lower, "rate": rate}


class TestVerdictOrdering(unittest.TestCase):
    def test_worse_prefers_fail(self):
        self.assertEqual(worse(PASS, FAIL), FAIL)
        self.assertEqual(worse(FAIL, PASS), FAIL)
        self.assertEqual(worse(FLAG, FAIL), FAIL)

    def test_worse_prefers_flag_over_pass(self):
        self.assertEqual(worse(PASS, FLAG), FLAG)
        self.assertEqual(worse(FLAG, PASS), FLAG)

    def test_worse_identity(self):
        for v in (PASS, FLAG, FAIL):
            self.assertEqual(worse(v, v), v)


class TestClampInvariant(unittest.TestCase):
    """I3: agent may lower, never raise."""

    def test_agent_cannot_raise_fail_ceiling(self):
        self.assertEqual(clamp_verdict(PASS, FAIL), FAIL)
        self.assertEqual(clamp_verdict(FLAG, FAIL), FAIL)

    def test_agent_cannot_raise_flag_ceiling(self):
        self.assertEqual(clamp_verdict(PASS, FLAG), FLAG)

    def test_agent_can_lower_below_ceiling(self):
        self.assertEqual(clamp_verdict(FAIL, PASS), FAIL)
        self.assertEqual(clamp_verdict(FLAG, PASS), FLAG)

    def test_exhaustive_never_exceeds_ceiling(self):
        order = {PASS: 2, FLAG: 1, FAIL: 0}
        for agent in (PASS, FLAG, FAIL):
            for ceiling in (PASS, FLAG, FAIL):
                out = clamp_verdict(agent, ceiling)
                self.assertLessEqual(order[out], order[ceiling])
                self.assertLessEqual(order[out], order[agent])


class TestScheduleChecks(unittest.TestCase):
    def test_valid_single_bracket_full_lp(self):
        self.assertEqual(check_schedule([bracket(0, 10_000_000)]), [])

    def test_empty_schedule_fails(self):
        findings = check_schedule([])
        self.assertEqual(findings[0][1], FAIL)

    def test_too_many_brackets_fails(self):
        findings = check_schedule([bracket(i, 1000) for i in range(33)])
        self.assertTrue(any(f[1] == FAIL for f in findings))

    def test_zero_rate_fails(self):
        findings = check_schedule([bracket(0, 0)])
        self.assertTrue(any(f[0] == "schedule_invalid_rate" for f in findings))

    def test_rate_above_max_fails(self):
        findings = check_schedule([bracket(0, 10_000_001)])
        self.assertTrue(any(f[0] == "schedule_invalid_rate" for f in findings))

    def test_first_threshold_nonzero_fails(self):
        findings = check_schedule([bracket(5, 1_000_000)])
        self.assertTrue(any(f[0] == "schedule_first_threshold" for f in findings))

    def test_non_ascending_fails(self):
        findings = check_schedule([bracket(0, 1_000_000), bracket(100, 1_000_000),
                                   bracket(100, 1_000_000)])
        self.assertTrue(any(f[0] == "schedule_not_ascending" for f in findings))

    def test_low_terminal_lp_rate_flagged(self):
        # 99% of raise to LP below 1000, then 1% above — classic drain shape:
        # look generous early, keep the real money.
        findings = check_schedule([bracket(0, 9_900_000), bracket(1000, 100_000)])
        names = [f[0] for f in findings]
        self.assertIn("schedule_low_terminal_lp", names)
        self.assertTrue(all(f[1] != FAIL for f in findings))

    def test_healthy_terminal_rate_not_flagged(self):
        findings = check_schedule([bracket(0, 5_000_000), bracket(1000, 8_000_000)])
        self.assertEqual(findings, [])


class TestPositionChecks(unittest.TestCase):
    def _pos(self, lo, hi, w):
        return {"offsetLower": lo, "offsetUpper": hi, "weight": w,
                "overridePositionRecipient": ZERO_ADDRESS}

    def test_empty_positions_ok(self):
        self.assertEqual(check_positions([]), [])

    def test_weight_overflow_fails(self):
        findings = check_positions([self._pos(-100, 100, 6_000_000),
                                    self._pos(-200, 200, 6_000_000)])
        self.assertTrue(any(f[0] == "positions_weight_overflow" for f in findings))

    def test_inverted_range_fails(self):
        findings = check_positions([self._pos(100, -100, 1_000_000)])
        self.assertTrue(any(f[0] == "position_inverted_range" for f in findings))

    def test_full_range_sentinel_ok(self):
        findings = check_positions([self._pos(MIN_TICK, MAX_TICK, 1_000_000)])
        self.assertEqual(findings, [])


class TestPoolChecks(unittest.TestCase):
    def _pool(self, fee, hook=ZERO_ADDRESS):
        return {"fee": fee, "tickSpacing": 60, "hook": hook}

    def test_normal_fee_hookless_clean(self):
        self.assertEqual(check_pool(self._pool(3000)), [])

    def test_dynamic_fee_flagged(self):
        findings = check_pool(self._pool(DYNAMIC_FEE_FLAG))
        self.assertTrue(any(f[0] == "pool_dynamic_fee" for f in findings))

    def test_extreme_fee_flagged(self):
        findings = check_pool(self._pool(500_000))  # 50% LP fee
        self.assertTrue(any(f[0] == "pool_extreme_fee" for f in findings))

    def test_nonzero_hook_flagged_for_judgment(self):
        findings = check_pool(self._pool(3000, hook="0x" + "aa" * 20))
        self.assertTrue(any(f[0] == "pool_nonzero_hook" for f in findings))


class TestRecipientChecks(unittest.TestCase):
    def test_contract_recipient_clean(self):
        facts = {"address": "0x1", "code_size": 100, "nonce": 1, "balance_wei": 0}
        self.assertEqual(check_recipient(facts), [])

    def test_fresh_eoa_flagged_with_detail(self):
        facts = {"address": "0x1", "code_size": 0, "nonce": 0, "balance_wei": 0}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][0], "recipient_eoa")
        self.assertIn("fresh EOA", findings[0][2])

    def test_active_eoa_flagged(self):
        facts = {"address": "0x1", "code_size": 0, "nonce": 500, "balance_wei": 10}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][1], FLAG)


if __name__ == "__main__":
    unittest.main()
