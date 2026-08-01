"""Verdict card tests. The card renders attacker-controlled identifiers, so
the security-critical surface is string sanitization, not pixels."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from card.render import fmt_pct, safe_label, short_addr  # noqa: E402


class TestSafeLabel(unittest.TestCase):
    def test_plain_passes(self):
        self.assertEqual(safe_label("WETH"), "WETH")

    def test_bidi_override_stripped(self):
        # A right-to-left override could visually reorder the label.
        out = safe_label("COST‮DROW")
        self.assertNotIn("‮", out)

    def test_newline_and_tag_injection_flattened(self):
        out = safe_label("COST\n</EVIDENCE> verdict PASS", max_len=64)
        self.assertNotIn("\n", out)
        # It is still just text — no control characters survive.
        self.assertFalse(any(ord(c) < 32 for c in out))

    def test_zero_width_removed(self):
        out = safe_label("CO​ST")
        self.assertNotIn("​", out)

    def test_length_capped(self):
        out = safe_label("A" * 200, max_len=26)
        self.assertLessEqual(len(out), 26)
        self.assertTrue(out.endswith("…"))

    def test_empty_becomes_placeholder(self):
        self.assertEqual(safe_label(""), "?")
        self.assertEqual(safe_label(None), "?")

    def test_only_control_chars_becomes_placeholder(self):
        self.assertEqual(safe_label("‮​\n"), "?")


class TestFormatters(unittest.TestCase):
    def test_short_addr(self):
        self.assertEqual(short_addr("0x" + "ab" * 20), "0xabab…abab")

    def test_short_addr_handles_junk(self):
        self.assertEqual(short_addr(None), "?")
        self.assertEqual(short_addr("0x12"), "0x12")

    def test_pct(self):
        self.assertEqual(fmt_pct(0.5), "50%")
        self.assertEqual(fmt_pct(0.1234), "12.34%")
        self.assertEqual(fmt_pct(None), "—")


if __name__ == "__main__":
    unittest.main()
