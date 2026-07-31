"""Minimal JSON-RPC client for Robinhood Chain. No web3 dependency.

Invariant I6: RPC failure raises RpcError — callers must skip/retry,
never substitute a guess. An unreachable RPC is "unknown", not "not found".
"""

import json
import time
from typing import Any, List, Optional

import requests

from .constants import DEFAULT_RPC


class RpcError(Exception):
    """RPC transport or node error. Facts derived from this call are UNKNOWN."""


class Rpc:
    def __init__(self, url: str = DEFAULT_RPC, timeout: int = 15, retries: int = 3):
        self.url = url
        self.timeout = timeout
        self.retries = retries
        self._id = 0

    def call(self, method: str, params: list) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        last_err: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                resp = requests.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                body = resp.json()
                if "error" in body:
                    raise RpcError("%s: %s" % (method, body["error"]))
                if "result" not in body:
                    raise RpcError("%s: malformed response (no result, no error)" % method)
                return body["result"]
            except (requests.RequestException, json.JSONDecodeError) as e:
                last_err = e
                time.sleep(1 + attempt)
        raise RpcError("%s failed after %d retries: %s" % (method, self.retries, last_err))

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
