"""RHJ official stock-token registry.

The issuer (Robinhood Assets, Jersey) publishes the canonical list of the
stock tokens it has deployed. Membership in that list is the only thing
that makes "verified official" true: a name is a claim, an address in the
issuer's registry is a fact.

Trust note, carried openly: this is our one off-chain dependency. The
registry is fetched from the issuer, cached to disk with the block height
and a fetch marker, and every consumer distinguishes three states:

  member      — address is in the cached registry     -> official (fact)
  non-member  — address is absent from a cache we
                believe is current                    -> not official
  unknown     — no cache, or the cache is unusable    -> refuse to judge
                                                         authenticity

The third state is the point. A missing or unreadable cache must never
silently collapse into "not official", because that would turn an
infrastructure failure into an accusation (I5: unreachable is not absent).
"""

import json
import os
from typing import Dict, Optional

REGISTRY_URL = "https://api.robinhood.com/rhj/assets"
CHAIN_ID = 4663
CACHE_PATH = os.path.join(os.path.dirname(__file__), "rhj_registry.json")

MEMBER = "member"
NON_MEMBER = "non_member"
UNKNOWN = "unknown"


class Registry:
    """Loaded issuer registry. `available` is false when we have no usable
    cache — callers must then treat authenticity as unknown, not false."""

    def __init__(self, entries: Optional[Dict[str, dict]]):
        self.entries = entries or {}
        self.available = entries is not None

    def status(self, address: Optional[str]) -> str:
        if not self.available:
            return UNKNOWN
        if not address:
            return UNKNOWN
        return MEMBER if address.lower() in self.entries else NON_MEMBER

    def get(self, address: Optional[str]) -> Optional[dict]:
        if not address:
            return None
        return self.entries.get(address.lower())

    def __len__(self) -> int:
        return len(self.entries)


def load(path: str = CACHE_PATH) -> Registry:
    """Load the cached registry. A missing or corrupt cache yields an
    unavailable Registry rather than an empty one, so absence of data can
    never be mistaken for absence of membership."""
    try:
        with open(path) as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return Registry(None)
    if not isinstance(raw, dict) or not raw:
        return Registry(None)
    return Registry({k.lower(): v for k, v in raw.items()})


def refresh(path: str = CACHE_PATH, timeout: int = 30) -> int:
    """Fetch the issuer registry and rewrite the cache atomically.

    Returns the number of chain-4663 deployments written. Raises on
    transport failure so a scheduled refresh fails loudly instead of
    quietly leaving a stale cache behind an exit code of zero.
    """
    import tempfile

    import requests

    body = requests.get(REGISTRY_URL, timeout=timeout).json()
    entries = {}
    for asset in body.get("assets", []):
        for dep in asset.get("deployments", []):
            if dep.get("chainId") == CHAIN_ID:
                entries[dep["contractAddress"].lower()] = {
                    "symbol": asset.get("tokenSymbol"),
                    "name": asset.get("tokenName"),
                }
    if not entries:
        raise RuntimeError("issuer returned no chain-%d deployments" % CHAIN_ID)

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".reg-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(entries, f, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return len(entries)


if __name__ == "__main__":
    print("wrote %d official stock tokens" % refresh())
