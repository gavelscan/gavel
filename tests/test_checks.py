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
    INFO,
    PASS,
    affects_ceiling,
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

    def test_drain_shape_fails(self):
        # Generous below the threshold, 1% above it: the real money never
        # reaches liquidity. This is the shape a FAIL exists for.
        findings = check_schedule([bracket(0, 9_900_000), bracket(1000, 100_000)])
        self.assertIn("exit_drain", [f[0] for f in findings])
        self.assertIn(FAIL, [f[1] for f in findings])

    def test_heavy_exit_flags(self):
        findings = check_schedule([bracket(0, 3_000_000)])
        self.assertIn("exit_heavy", [f[0] for f in findings])
        self.assertIn(FLAG, [f[1] for f in findings])

    def test_partial_exit_is_context_not_warning(self):
        # 80% to liquidity is worth stating and not worth warning about.
        findings = check_schedule([bracket(0, 8_000_000)])
        self.assertEqual([f[0] for f in findings], ["exit_partial"])
        self.assertEqual(findings[0][1], INFO)

    def test_full_routing_says_nothing(self):
        # Routing the whole raise is what 83% of the record does. Silence.
        self.assertEqual(check_schedule([bracket(0, 10_000_000)]), [])


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
    """Paying an ordinary wallet is the base rate — 85% of the record — so
    it is context. Only an unproven wallet is a warning."""

    def test_contract_recipient_is_context(self):
        facts = {"address": "0x1", "code_size": 100, "nonce": 1, "balance_wei": 0}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][0], "recipient_contract")
        self.assertEqual(findings[0][1], INFO)

    def test_never_used_wallet_flags(self):
        facts = {"address": "0x1", "code_size": 0, "nonce": 0, "balance_wei": 0}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][0], "recipient_fresh")
        self.assertEqual(findings[0][1], FLAG)

    def test_barely_used_wallet_flags(self):
        facts = {"address": "0x1", "code_size": 0, "nonce": 2, "balance_wei": 0}
        self.assertEqual(check_recipient(facts)[0][1], FLAG)

    def test_active_wallet_is_context_not_warning(self):
        facts = {"address": "0x1", "code_size": 0, "nonce": 500, "balance_wei": 10}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][0], "recipient_eoa")
        self.assertEqual(findings[0][1], INFO)

    def test_delegated_wallet_is_not_a_contract(self):
        """EIP-7702: 23 bytes of 0xef0100||address is a wallet, not a
        contract. 39 of the 40 code-bearing recipients in the record are
        this shape; calling them contracts published a false statement on
        75 launches."""
        facts = {"address": "0x1", "code_size": 23, "delegated": True,
                 "delegate": "0x" + "ab" * 20, "nonce": 7, "balance_wei": 0}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][0], "recipient_delegated_wallet")
        self.assertEqual(findings[0][1], INFO)

    def test_delegated_wallet_never_claims_history(self):
        """A delegate spends the account's nonce too, so 'never sent a
        transaction' is not a claim we can make about a delegated wallet
        — even at nonce 0 it must not FLAG as fresh."""
        facts = {"address": "0x1", "code_size": 23, "delegated": True,
                 "delegate": "0x" + "ab" * 20, "nonce": 0, "balance_wei": 0}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][0], "recipient_delegated_wallet")
        self.assertEqual(findings[0][1], INFO)

    def test_real_contract_still_reported(self):
        """The one genuine contract recipient in the record must keep its
        label — the delegation carve-out must not swallow it."""
        facts = {"address": "0x1", "code_size": 45, "delegated": False,
                 "delegate": None, "nonce": 1, "balance_wei": 0}
        findings = check_recipient(facts)
        self.assertEqual(findings[0][0], "recipient_contract")


class TestDelegatedAssessment(unittest.TestCase):
    """derive_assessments hard-fixes the recipient label, so the judge can
    never correct a mistake made here. The delegation test must win."""

    def _sheet(self, recipient):
        return {
            "launch": {"params": {"pool": {"hook": ZERO_ADDRESS},
                                  "currency": ZERO_ADDRESS}},
            "recipient": recipient,
            "currency": {"kind": "native_eth", "official": False,
                         "registry_status": "unknown"},
        }

    def test_delegated_wallet_fixed_as_delegated(self):
        from gavel.checks import derive_assessments
        rules = derive_assessments(self._sheet(
            {"code_size": 23, "delegated": True, "nonce": 5}))
        self.assertEqual(rules["recipient_assessment"],
                         {"fixed": "delegated_wallet"})

    def test_true_contract_fixed_as_contract(self):
        from gavel.checks import derive_assessments
        rules = derive_assessments(self._sheet(
            {"code_size": 45, "delegated": False, "nonce": 5}))
        self.assertEqual(rules["recipient_assessment"], {"fixed": "contract"})


class TestInfoNeverMovesTheCeiling(unittest.TestCase):
    """The whole point of INFO: it is published, and it changes nothing.
    A calibration that let context cap a verdict is what produced 88% FLAG."""

    def test_affects_ceiling(self):
        self.assertTrue(affects_ceiling(PASS))
        self.assertTrue(affects_ceiling(FLAG))
        self.assertTrue(affects_ceiling(FAIL))
        self.assertFalse(affects_ceiling(INFO))

    def test_info_only_findings_leave_pass(self):
        from gavel.checks import worse
        ceiling = PASS
        for _sev in (INFO, INFO, INFO):
            if affects_ceiling(_sev):
                ceiling = worse(ceiling, _sev)
        self.assertEqual(ceiling, PASS)


if __name__ == "__main__":
    unittest.main()
