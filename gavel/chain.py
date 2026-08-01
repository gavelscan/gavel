"""Minimal JSON-RPC client for Robinhood Chain. No web3 dependency.

Invariant I6: RPC failure raises RpcError — callers must skip/retry,
never substitute a guess. An unreachable RPC is "unknown", not "not found".
"""

import json
import time
from typing import Any, List, Optional

import requests

import os

from .constants import DEFAULT_RPC, FALLBACK_RPCS


class RpcError(Exception):
    """RPC transport or node error. Facts derived from this call are UNKNOWN."""


class Rpc:
    """A client that treats one flaky endpoint as a transport problem, not
    as evidence about the chain.

    Node errors (a revert, a bad parameter) are the chain answering and are
    raised immediately. Transport failures are retried, then the next
    endpoint is tried, because a dropped connection must never be allowed
    to read as "this launch does not exist".
    """

    def __init__(self, url: Optional[str] = None, timeout: int = 15,
                 retries: int = 2):
        env = os.environ.get("GAVEL_RPCS")
        if url:
            self.urls = [url]
        elif env:
            self.urls = [u.strip() for u in env.split(",") if u.strip()]
        else:
            self.urls = list(FALLBACK_RPCS)
        self.url = self.urls[0]
        self.timeout = timeout
        self.retries = retries
        self._id = 0
        self._preferred = 0

    def call(self, method: str, params: list) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        last_err: Optional[Exception] = None
        order = self.urls[self._preferred:] + self.urls[:self._preferred]

        for idx, url in enumerate(order):
            for attempt in range(self.retries):
                try:
                    resp = requests.post(url, json=payload, timeout=self.timeout)
                    resp.raise_for_status()
                    body = resp.json()
                    if "error" in body:
                        # The node answered. That is a fact, not an outage —
                        # do not retry it against another endpoint.
                        raise RpcError("%s: %s" % (method, body["error"]))
                    if "result" not in body:
                        raise RpcError(
                            "%s: malformed response (no result, no error)" % method)
                    # Stick with whatever endpoint is currently working.
                    self._preferred = (self._preferred + idx) % len(self.urls)
                    self.url = url
                    return body["result"]
                except (requests.RequestException, json.JSONDecodeError) as e:
                    last_err = e
                    time.sleep(0.5 * (attempt + 1))
        raise RpcError("%s failed on %d endpoint(s): %s"
                       % (method, len(self.urls), last_err))

    # -- convenience wrappers -------------------------------------------------

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def get_code_size(self, address: str) -> int:
        code = self.call("eth_getCode", [address, "latest"])
        return max(0, len(code) // 2 - 1)

    def get_nonce(self, address: str) -> int:
        return int(self.call("eth_getTransactionCount", [address, "latest"]), 16)

    def get_balance(self, address: str) -> int:
        return int(self.call("eth_getBalance", [address, "latest"]), 16)

    def eth_call(self, to: str, data: str) -> str:
        return self.call("eth_call", [{"to": to, "data": data}, "latest"])

    def get_logs(self, address, topics: List[Any],
                 from_block: int, to_block: int) -> list:
        """address may be a single address or a list; topics follows the
        eth_getLogs positional-OR convention (a list at a position ORs)."""
        return self.call("eth_getLogs", [{
            "address": address,
            "topics": topics,
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
        }])

    # -- typed contract reads -------------------------------------------------

    SEL_SYMBOL = "0x95d89b41"        # symbol()
    SEL_NAME = "0x06fdde03"          # name()
    SEL_TOTAL_SUPPLY = "0x18160ddd"  # totalSupply()
    SEL_LBP_PARAMS = "0xe1d97d1f"    # lbpInitializationParams()

    def auction_outcome(self, initializer: str):
        """What the auction itself says about how it ended.

        The chain emits no event for an auction that failed to draw bids:
        it simply sits past its migration block in silence, which looks
        identical to one that cleared and was never migrated. The
        initializer distinguishes them — it reverts until a clearing price
        exists — so this is the only way to tell "nobody bid" from "nobody
        pressed the button".

        Returns {"cleared": bool, "sold": int, "raised": int}. A revert
        means not cleared; an RPC failure propagates, because unreachable
        is not the same as unfilled (I5).
        """
        try:
            raw = self.eth_call(initializer, self.SEL_LBP_PARAMS)
        except RpcError as e:
            if "revert" in str(e).lower():
                return {"cleared": False, "sold": 0, "raised": 0}
            raise
        if not raw or raw == "0x" or len(raw) < 2 + 192:
            return {"cleared": False, "sold": 0, "raised": 0}
        b = bytes.fromhex(raw[2:])
        return {
            "cleared": True,
            "sold": int.from_bytes(b[32:64], "big"),
            "raised": int.from_bytes(b[64:96], "big"),
        }

    def read_string(self, to: str, selector: str) -> Optional[str]:
        """Read a string-returning view. None means the call reverted or
        returned undecodable data — an unknown, not an empty string."""
        try:
            raw = self.eth_call(to, selector)
        except RpcError:
            raise
        if raw is None or raw == "0x":
            return None
        try:
            blob = bytes.fromhex(raw[2:])
            offset = int.from_bytes(blob[0:32], "big")
            length = int.from_bytes(blob[offset:offset + 32], "big")
            return blob[offset + 32:offset + 32 + length].decode("utf-8", "replace")
        except Exception:
            return None

    def read_uint(self, to: str, selector: str) -> Optional[int]:
        try:
            raw = self.eth_call(to, selector)
        except RpcError:
            raise
        if raw is None or raw == "0x":
            return None
        return int(raw, 16)

    def read_address(self, to: str, selector: str) -> Optional[str]:
        try:
            raw = self.eth_call(to, selector)
        except RpcError:
            raise
        if raw is None or raw == "0x" or len(raw) < 66:
            return None
        return "0x" + raw[-40:]
