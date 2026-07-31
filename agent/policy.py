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

# Instruction-shaped content: an attacker telling the judge what to do.
_INJECTION_MARKERS = (
    "ignore previous", "ignore all", "disregard", "system:", "assistant:",
    "you are", "verdict", "manipulation", "instruction", "evidence",
    "prompt", "override", "retraction", "prior", "respond with",
    "reply with", "output", "classify", "rate this", "mark as", "treat this",
    "note to", "reviewer", "judge",
)

# Trust-claim content: an attacker asserting legitimacy in a field that is
# supposed to be a name. A token cannot vouch for itself, so any of this in
# a name/symbol is manipulation-shaped even without an imperative.
_TRUST_CLAIM_MARKERS = (
    "audited", "audit by", "certik", "verified", "official", "legitimate",
    "endorsed", "approved", "safe", "trusted", "kyc", "no rug", "renounced",
    "benign", "authentic", "genuine", "partnership",
)

# Homoglyph folding: Cyrillic/Greek lookalikes that survive NFKC.
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "х": "x", "у": "y", "і": "i", "ј": "j", "һ": "h",
    "ο": "o", "α": "a", "ε": "e", "ρ": "p", "ν": "v",
})

MAX_NAME_LEN = 96


def _normalize(text: str) -> str:
    """Fold the evasions that keep a string legible to a model while
    hiding it from a naive substring scan: compatibility forms
    (fullwidth), homoglyphs, and inserted separators."""
    folded = unicodedata.normalize("NFKC", text).lower().translate(_HOMOGLYPHS)
    # Collapse separator-spaced text ("i g n o r e" -> "ignore") while
    # keeping a spaced copy so multi-word markers still match.
    collapsed = re.sub(r"[\s._\-*|]+", "", folded)
    spaced = re.sub(r"\s+", " ", folded)
    return spaced + " " + collapsed


def injection_signal(factsheet: dict) -> List[str]:
    """Scan attacker-controlled strings for injection-shaped content.

    Deterministic and independent of the model, so an injection that
    silences the model's own flag cannot silence this one. Normalization
    is applied first, because an evasion that defeats this scan is only
    useful to an attacker if the model still reads it as instructions —
    and NFKC/homoglyph/spacing folding covers exactly that gap.

    This is a detector, not a proof: it raises the cost of a silent
    injection, it does not eliminate the class. The structural defenses
    (no free text, fact-bounded assessments, clamp) are what make a
    missed signal survivable.
    """
    signals = []
    currency = factsheet.get("currency", {}) or {}
    candidates = [
        ("currency.name", currency.get("name")),
        ("currency.symbol", currency.get("symbol")),
    ]
    for label, value in candidates:
        if not isinstance(value, str):
            continue
        haystack = _normalize(value)
        for marker in _INJECTION_MARKERS:
            if marker in haystack or marker.replace(" ", "") in haystack:
                signals.append("%s contains instruction marker %r" % (label, marker))
        for marker in _TRUST_CLAIM_MARKERS:
            if marker in haystack or marker.replace(" ", "") in haystack:
                signals.append("%s contains self-asserted trust claim %r"
                               % (label, marker))
        if any(c in value for c in "\n\r\t"):
            signals.append("%s contains a control character" % label)
        if len(value) > MAX_NAME_LEN:
            signals.append("%s abnormally long (%d chars)" % (label, len(value)))
        if unicodedata.normalize("NFKC", value) != value:
            signals.append("%s uses non-canonical unicode forms" % label)
        if any(ord(c) > 0x7F and unicodedata.category(c).startswith("L")
               for c in value.translate(_HOMOGLYPHS)):
            signals.append("%s mixes non-ASCII letters" % label)
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
