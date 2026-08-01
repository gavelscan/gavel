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



class TestRegistryStates(unittest.TestCase):
    """The registry's third state is the safety property: a cache we cannot
    read must never be reported as 'not official'."""

    def setUp(self):
        from gavel import registry
        self.registry = registry

    def test_missing_cache_is_unknown_not_absent(self):
        reg = self.registry.load("/nonexistent/registry.json")
        self.assertFalse(reg.available)
        self.assertEqual(reg.status("0x" + "aa" * 20), self.registry.UNKNOWN)

    def test_corrupt_cache_is_unknown(self):
        import tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        f.write("{not json")
        f.close()
        try:
            self.assertEqual(self.registry.load(f.name).status("0x1"),
                             self.registry.UNKNOWN)
        finally:
            os.unlink(f.name)

    def test_member_and_non_member(self):
        import json as _json
        import tempfile
        addr = "0x" + "AB" * 20
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        _json.dump({addr: {"symbol": "COST", "name": "Costco"}}, f)
        f.close()
        try:
            reg = self.registry.load(f.name)
            self.assertTrue(reg.available)
            # Casing must not defeat membership.
            self.assertEqual(reg.status(addr.lower()), self.registry.MEMBER)
            self.assertEqual(reg.get(addr.lower())["symbol"], "COST")
            self.assertEqual(reg.status("0x" + "cd" * 20),
                             self.registry.NON_MEMBER)
        finally:
            os.unlink(f.name)

    def test_live_cache_loads(self):
        reg = self.registry.load()
        self.assertTrue(reg.available)
        self.assertGreater(len(reg), 50)


if __name__ == "__main__":
    unittest.main()
