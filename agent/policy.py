"""Policy controls enforced OUTSIDE the model.

After the schema redesign the model emits no free text, so the deny-list
and number guard are no longer the last line before the feed — they now
harden the CARD layer (which renders our own strings) as belt-and-
suspenders. What remains genuinely load-bearing here:

- injection_signal(): a DETERMINISTIC detector over attacker-controlled
  strings. The model's self-reported manipulation flag can be silenced by
  a good-enough injection; this cannot, because the model never sees it.
  The judge ORs the two, so manipulation is flagged if EITHER fires.
- armed() / kill switch: publishing needs GAVEL_ARMED=1 and no kill file,
  keyed off an ABSOLUTE path so it works under any CWD (systemd, cron).
- RateLimiter: a runaway loop cannot flood the feed.
"""

import os
import re
import unicodedata
from typing import List

# --- number guard (card layer) ----------------------------------------------

_SPELLED_NUMBERS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "million", "billion", "half", "quarter", "third", "tenth",
    "double", "triple", "twice", "dozen",
}


def has_number(text: str) -> bool:
    """True if the text contains any number: an ASCII/Unicode digit, a
    Unicode numeric character (superscripts, Roman numerals, circled
    digits), or a spelled-out number word."""
    for ch in text:
        if ch.isdigit():
            return True
        # Unicode numeric category N* beyond decimal digits (No, Nl).
        if unicodedata.category(ch).startswith("N"):
            return True
        if unicodedata.numeric(ch, None) is not None:
            return True
    words = re.findall(r"[a-z]+", text.lower())
    return any(w in _SPELLED_NUMBERS for w in words)


# --- trade-advice deny-list (card layer) ------------------------------------

_DENY_TERMS = (
    "buy", "sell", "buying", "selling", "ape", "aping", "gem", "moon",
    "mooning", "pump", "dump", "guaranteed", "guarantee", "profit",
    "bullish", "bearish", "dyor", "wagmi", "degen", "hodl",
    "accumulate", "acquire", "scoop", "load up", "grab a bag", "send it",
    "get in", "don't wait", "do not wait", "last chance", "before it",
    "don't miss", "do not miss", "ape in",
)
_DENY_PATTERNS = [re.compile(r"\b%s\b" % re.escape(t), re.IGNORECASE)
                  for t in _DENY_TERMS]


def text_violations(text: str) -> List[str]:
    """Reasons a piece of user-facing text is unpublishable. Applied by
    the card layer to rendered copy (defense in depth)."""
    violations = []
    for pattern in _DENY_PATTERNS:
        if pattern.search(text):
            violations.append("deny-list term %r" % pattern.pattern)
    if has_number(text):
        violations.append("number in prose — figures must be rendered from facts")
    return violations


# --- deterministic injection detection (load-bearing) -----------------------

_INJECTION_MARKERS = (
    "ignore previous", "ignore all previous", "disregard", "system:",
    "assistant:", "you are", "verdict", "manipulation_detected",
    "instruction", "<<evidence", "end evidence", "</evidence", "<evidence",
    "prompt", "override", "retraction", "prior evidence",
)


def injection_signal(factsheet: dict) -> List[str]:
    """Scan attacker-controlled strings for injection-shaped content.
    Deterministic and independent of the model, so an injection that
    silences the model's own flag cannot silence this one."""
    signals = []
    currency = factsheet.get("currency", {}) or {}
    candidates = [
        ("currency.name", currency.get("name")),
        ("currency.symbol", currency.get("symbol")),
    ]
    for label, value in candidates:
        if not isinstance(value, str):
            continue
        low = value.lower()
        for marker in _INJECTION_MARKERS:
            if marker in low:
                signals.append("%s contains %r" % (label, marker))
        if "\n" in value or "\r" in value:
            signals.append("%s contains a newline" % label)
        if len(value) > 96:
            signals.append("%s abnormally long (%d chars)" % (label, len(value)))
    return signals


# --- publishing gate --------------------------------------------------------

def _default_kill_file() -> str:
    """Absolute path so the kill switch works under any CWD."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "data", "KILL")


def armed() -> bool:
    if os.environ.get("GAVEL_ARMED") != "1":
        return False
    kill_file = os.environ.get("GAVEL_KILL_FILE") or _default_kill_file()
    if not os.path.isabs(kill_file):
        # A relative kill path is a misconfiguration of a safety control:
        # refuse to arm rather than silently checking the wrong location.
        return False
    if os.path.exists(kill_file):
        return False
    return True


class RateLimiter:
    """Token bucket over a sliding window. Clock injectable for tests."""

    def __init__(self, max_events: int, window_seconds: float, clock=None):
        import time
        self.max_events = max_events
        self.window = window_seconds
        self.clock = clock or time.monotonic
        self._events: List[float] = []

    def allow(self) -> bool:
        now = self.clock()
        self._events = [t for t in self._events if now - t < self.window]
        if len(self._events) >= self.max_events:
            return False
        self._events.append(now)
        return True
