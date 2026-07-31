"""Watcher: follow every Liquidity Launcher launch on Robinhood Chain.

Fail-closed by design (Invariants I4/I5): an RPC error aborts the scan
cycle without advancing the cursor, so a flaky node can delay facts but
never silently drop a launch. A confirmation lag keeps reorg-vulnerable
blocks out of the archive.

Coverage contract: the cursor (`last_scanned`) only ever advances over
ranges that were actually fetched and archived. A backfill that would
leave a gap between existing coverage and its starting block archives
its events but refuses to move the cursor.

Filtering happens client-side: the eth_getLogs query filters by address
only, so a protocol upgrade that adds new event types shows up in the
archive as Unknown/DecodeFailed records instead of being silently
excluded by a stale topic list.

Archive format: JSONL, one decoded event per line, deduplicated by
(tx.lower(), log_index) — within a batch, across batches, and across
restarts. The archive is append-only.
"""

import json
import os
import tempfile
import time
from typing import List, Optional, Tuple

from .chain import Rpc, RpcError
from .constants import LBP_STRATEGY, LIQUIDITY_LAUNCHER
from .decode import decode_any

WATCHED_ADDRESSES = [LIQUIDITY_LAUNCHER, LBP_STRATEGY]

# Below this span we stop bisecting and let the error propagate: a range
# this small failing repeatedly is a broken node, not an oversized query.
MIN_BISECT_SPAN = 128


def _record_key(rec: dict) -> Tuple[str, int]:
    # tx hashes are normalized: hex casing differs across node vendors.
    return (rec["tx"].lower(), rec["log_index"])


class Watcher:
    def __init__(self, rpc: Rpc, data_dir: str = "data", confirmations: int = 32):
        self.rpc = rpc
        self.confirmations = confirmations
        self.data_dir = data_dir
        self.state_path = os.path.join(data_dir, "state.json")
        self.archive_path = os.path.join(data_dir, "events.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        self._seen = self._load_seen()

    # -- persistence ----------------------------------------------------------

    def _load_state(self) -> dict:
        if not os.path.exists(self.state_path):
            return {"last_scanned": -1}
        with open(self.state_path) as f:
            return json.load(f)

    def _save_state(self, state: dict) -> None:
        """Atomic write: a crash mid-save must never leave a torn state
        file that would silently skip a block range on restart."""
        fd, tmp = tempfile.mkstemp(dir=self.data_dir, prefix=".state-")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.replace(tmp, self.state_path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _load_seen(self) -> set:
        """Rebuild the dedup set from the archive.

        A torn FINAL line (crash mid-append) is truncated away — not just
        skipped, or the next append would bury it mid-file and poison
        every later restart. Truncation is safe: the cursor only advances
        after a fully archived range, so the torn record's range will be
        re-fetched and re-archived intact. A torn line anywhere else is
        real corruption and raises — fail closed, never guess.
        """
        seen = set()
        if not os.path.exists(self.archive_path):
            return seen
        with open(self.archive_path, "rb") as f:
            lines = f.read().splitlines(keepends=True)
        clean_bytes = 0
        for i, raw_line in enumerate(lines):
            line = raw_line.strip()
            if line:
                try:
                    rec = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    if i == len(lines) - 1:
                        with open(self.archive_path, "r+b") as f:
                            f.truncate(clean_bytes)
                        break
                    raise
                seen.add(_record_key(rec))
            clean_bytes += len(raw_line)
        return seen

    # -- fetching -------------------------------------------------------------

    def _get_logs_adaptive(self, from_block: int, to_block: int) -> list:
        """Fetch watched logs (address filter only), bisecting the range
        when the node refuses.

        Bisection only helps oversized-range errors; a genuinely broken
        node keeps failing at MIN_BISECT_SPAN and the error propagates —
        fail closed, never fail empty.
        """
        try:
            return self.rpc.get_logs(WATCHED_ADDRESSES, [], from_block, to_block)
        except RpcError:
            if to_block - from_block < MIN_BISECT_SPAN:
                raise
            mid = (from_block + to_block) // 2
            return (self._get_logs_adaptive(from_block, mid)
                    + self._get_logs_adaptive(mid + 1, to_block))

    # -- scanning -------------------------------------------------------------

    def _process_logs(self, logs: list) -> List[dict]:
        """Decode, dedupe (incl. within the batch) and archive new logs.

        Each record is added to the dedup set immediately after its line
        is written, so an in-process retry after a partial write cannot
        re-archive the lines that already made it to disk.
        """
        logs = sorted(logs, key=lambda l: (int(l["blockNumber"], 16),
                                           int(l["logIndex"], 16)))
        fresh = []
        with open(self.archive_path, "a") as f:
            for log in logs:
                if log.get("removed"):
                    continue
                rec = decode_any(log)
                rec["log_index"] = int(log["logIndex"], 16)
                key = _record_key(rec)
                if key in self._seen:
                    continue
                f.write(json.dumps(rec, sort_keys=True) + "\n")
                self._seen.add(key)
                fresh.append(rec)
            f.flush()
            os.fsync(f.fileno())
        return fresh

    def scan_once(self) -> List[dict]:
        """Scan from the cursor to the confirmed head. Returns new records.

        State advances only after every log in the range is archived; any
        error leaves the cursor untouched so the range is rescanned.
        """
        state = self._load_state()
        head = self.rpc.block_number()
        safe_head = head - self.confirmations
        from_block = state["last_scanned"] + 1
        if safe_head < from_block:
            return []
        logs = self._get_logs_adaptive(from_block, safe_head)
        fresh = self._process_logs(logs)
        self._save_state({"last_scanned": safe_head})
        return fresh

    def backfill(self, from_block: int = 0, to_block: Optional[int] = None) -> List[dict]:
        """One-shot historical scan.

        The upper bound is always clamped to the confirmed head — an
        explicit to_block cannot reach into the reorg window or beyond
        the chain (nodes would silently truncate the response while we
        recorded full coverage). The cursor advances only when the
        scanned range is contiguous with existing coverage; otherwise
        events are archived but the cursor stays, because a cursor past
        an unscanned gap is a lie about coverage.
        """
        state = self._load_state()
        safe_head = self.rpc.block_number() - self.confirmations
        if to_block is None:
            to_block = safe_head
        else:
            to_block = min(to_block, safe_head)
        if to_block < from_block:
            return []
        logs = self._get_logs_adaptive(from_block, to_block)
        fresh = self._process_logs(logs)
        contiguous = from_block <= state["last_scanned"] + 1
        if contiguous and to_block > state["last_scanned"]:
            self._save_state({"last_scanned": to_block})
        elif not contiguous:
            print("backfill: gap [%d, %d] unscanned — cursor NOT advanced"
                  % (state["last_scanned"] + 1, from_block - 1))
        return fresh

    def run(self, interval: int = 30) -> None:
        """Poll forever. Errors are logged and retried next cycle — the
        loop must outlive node outages, and decode problems surface as
        DecodeFailed archive records rather than exceptions."""
        while True:
            try:
                fresh = self.scan_once()
                for rec in fresh:
                    print("[%s] %s tx=%s" % (rec["event"],
                                             rec.get("initializer",
                                                     rec.get("token", "")),
                                             rec["tx"]))
            except RpcError as e:
                print("scan failed, cursor not advanced: %s" % e)
            except Exception as e:  # unexpected — keep the loop alive, fail closed
                print("scan error (%s), cursor not advanced: %s"
                      % (type(e).__name__, e))
            time.sleep(interval)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="GAVEL launch watcher")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--rpc", default=None)
    ap.add_argument("--backfill", action="store_true",
                    help="scan history once and exit")
    ap.add_argument("--from-block", type=int, default=0)
    ap.add_argument("--interval", type=int, default=30)
    args = ap.parse_args()

    rpc = Rpc(args.rpc) if args.rpc else Rpc()
    watcher = Watcher(rpc, data_dir=args.data_dir)
    if args.backfill:
        fresh = watcher.backfill(from_block=args.from_block)
        by_event = {}
        for rec in fresh:
            by_event[rec["event"]] = by_event.get(rec["event"], 0) + 1
        print("archived %d new events: %s" % (len(fresh), by_event))
    else:
        watcher.run(interval=args.interval)


if __name__ == "__main__":
    main()
