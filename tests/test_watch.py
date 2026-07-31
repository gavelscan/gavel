"""Watcher tests: fail-closed scanning, dedup, bisection, persistence.

All offline — the RPC is faked, but the fake reimplements real
eth_getLogs filter semantics (case-insensitive address matching,
positional topic OR-lists). A fake that ignores the filters would keep
these tests green while a typoed address or topic silently matched
nothing in production — the exact failure class this suite exists to
prevent.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gavel.chain import RpcError  # noqa: E402
from gavel.constants import (  # noqa: E402
    LBP_STRATEGY,
    TOPIC_INITIALIZER_CREATED,
    TOPIC_MIGRATION_FAILED,
    TOPIC_TOKEN_CREATED,
)
from gavel.watch import MIN_BISECT_SPAN, Watcher  # noqa: E402


def make_log(block, log_index, topic0=TOPIC_TOKEN_CREATED, tx=None,
             address=LBP_STRATEGY, data="0x"):
    return {
        "address": address,
        "topics": [topic0, "0x" + "00" * 12 + "ab" * 20],
        "data": data,
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
        "transactionHash": tx or ("0x" + ("%064x" % (block * 1000 + log_index))),
    }


class FakeRpc:
    """Fake node honoring real eth_getLogs semantics."""

    def __init__(self, head=1000, logs=None, max_span=None, fail_always=False):
        self.head = head
        self.logs = logs or []
        self.max_span = max_span
        self.fail_always = fail_always
        self.get_logs_calls = []

    def block_number(self):
        return self.head

    @staticmethod
    def _match_address(log, address):
        wanted = address if isinstance(address, list) else [address]
        return log["address"].lower() in [a.lower() for a in wanted]

    @staticmethod
    def _match_topics(log, topics):
        for i, want in enumerate(topics):
            if want is None:
                continue
            wants = want if isinstance(want, list) else [want]
            if i >= len(log["topics"]):
                return False
            if log["topics"][i].lower() not in [w.lower() for w in wants]:
                return False
        return True

    def get_logs(self, address, topics, from_block, to_block):
        self.get_logs_calls.append((from_block, to_block))
        if self.fail_always:
            raise RpcError("node down")
        if self.max_span is not None and to_block - from_block > self.max_span:
            raise RpcError("range too large")
        return [l for l in self.logs
                if from_block <= int(l["blockNumber"], 16) <= min(to_block, self.head)
                and self._match_address(l, address)
                and self._match_topics(l, topics)]


class WatcherTestBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gavel-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def watcher(self, rpc, confirmations=32):
        return Watcher(rpc, data_dir=self.dir, confirmations=confirmations)

    def read_archive(self):
        path = os.path.join(self.dir, "events.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(l) for l in f if l.strip()]

    def read_state(self):
        with open(os.path.join(self.dir, "state.json")) as f:
            return json.load(f)


class TestScanOnce(WatcherTestBase):
    def test_archives_new_logs(self):
        rpc = FakeRpc(head=1000, logs=[make_log(100, 0), make_log(200, 1)])
        fresh = self.watcher(rpc).scan_once()
        self.assertEqual(len(fresh), 2)
        self.assertEqual(len(self.read_archive()), 2)

    def test_watched_address_filter_actually_matches(self):
        # Would fail if WATCHED_ADDRESSES had a typo: the faithful fake
        # filters by address exactly like a real node.
        rpc = FakeRpc(head=1000, logs=[make_log(100, 0),
                                       make_log(101, 0, address="0x" + "99" * 20)])
        fresh = self.watcher(rpc).scan_once()
        self.assertEqual(len(fresh), 1)

    def test_cursor_advances_to_confirmed_head_only(self):
        rpc = FakeRpc(head=1000)
        self.watcher(rpc, confirmations=32).scan_once()
        self.assertEqual(self.read_state()["last_scanned"], 968)

    def test_confirmation_lag_excludes_recent_blocks(self):
        rpc = FakeRpc(head=1000, logs=[make_log(990, 0)])
        fresh = self.watcher(rpc, confirmations=32).scan_once()
        self.assertEqual(fresh, [])

    def test_second_scan_picks_up_previously_unconfirmed(self):
        log = make_log(990, 0)
        rpc = FakeRpc(head=1000, logs=[log])
        w = self.watcher(rpc, confirmations=32)
        self.assertEqual(w.scan_once(), [])
        rpc.head = 1100
        fresh = w.scan_once()
        self.assertEqual(len(fresh), 1)

    def test_no_rescan_when_head_static(self):
        rpc = FakeRpc(head=1000)
        w = self.watcher(rpc)
        w.scan_once()
        calls_before = len(rpc.get_logs_calls)
        self.assertEqual(w.scan_once(), [])
        self.assertEqual(len(rpc.get_logs_calls), calls_before)

    def test_removed_logs_skipped(self):
        log = make_log(100, 0)
        log["removed"] = True
        rpc = FakeRpc(head=1000, logs=[log])
        self.assertEqual(self.watcher(rpc).scan_once(), [])

    def test_records_sorted_by_block_then_index(self):
        rpc = FakeRpc(head=1000, logs=[make_log(200, 5), make_log(100, 7),
                                       make_log(100, 2)])
        fresh = self.watcher(rpc).scan_once()
        order = [(r["block"], r["log_index"]) for r in fresh]
        self.assertEqual(order, sorted(order))


class TestFailClosed(WatcherTestBase):
    def test_error_leaves_cursor_untouched(self):
        rpc = FakeRpc(head=1000, fail_always=True)
        w = self.watcher(rpc)
        with self.assertRaises(RpcError):
            w.scan_once()
        self.assertFalse(os.path.exists(os.path.join(self.dir, "state.json")))

    def test_error_after_progress_rescans_range(self):
        rpc = FakeRpc(head=1000, logs=[make_log(100, 0)])
        w = self.watcher(rpc)
        w.scan_once()
        rpc.fail_always = True
        rpc.head = 2000
        with self.assertRaises(RpcError):
            w.scan_once()
        self.assertEqual(self.read_state()["last_scanned"], 968)

    def test_small_range_failure_propagates(self):
        rpc = FakeRpc(head=100 + MIN_BISECT_SPAN, fail_always=True)
        with self.assertRaises(RpcError):
            self.watcher(rpc, confirmations=0).scan_once()


class TestDedup(WatcherTestBase):
    def test_same_log_never_archived_twice_across_scans(self):
        log = make_log(100, 0)
        rpc = FakeRpc(head=1000, logs=[log])
        w = self.watcher(rpc)
        w.scan_once()
        w2 = self.watcher(rpc)
        os.unlink(os.path.join(self.dir, "state.json"))
        self.assertEqual(w2.scan_once(), [])
        self.assertEqual(len(self.read_archive()), 1)

    def test_duplicate_within_one_batch_archived_once(self):
        # Load-balanced RPC farms can return the same log twice in one
        # response; the archive must still contain it exactly once.
        log = make_log(100, 0)
        rpc = FakeRpc(head=1000, logs=[log, dict(log)])
        fresh = self.watcher(rpc).scan_once()
        self.assertEqual(len(fresh), 1)
        self.assertEqual(len(self.read_archive()), 1)

    def test_tx_hash_casing_does_not_defeat_dedup(self):
        tx = "0x" + "AB" * 32
        a = make_log(100, 0, tx=tx)
        b = make_log(100, 0, tx=tx.lower())
        rpc = FakeRpc(head=1000, logs=[a, b])
        fresh = self.watcher(rpc).scan_once()
        self.assertEqual(len(fresh), 1)

    def test_in_process_retry_after_write_does_not_duplicate(self):
        # _seen is updated per record at write time, so re-processing the
        # same batch on the same instance is a no-op.
        log = make_log(100, 0)
        rpc = FakeRpc(head=1000, logs=[log])
        w = self.watcher(rpc)
        w.scan_once()
        self.assertEqual(w._process_logs([log]), [])
        self.assertEqual(len(self.read_archive()), 1)

    def test_seen_reloaded_from_archive(self):
        log = make_log(100, 0)
        rpc = FakeRpc(head=1000, logs=[log])
        self.watcher(rpc).scan_once()
        w2 = self.watcher(rpc)
        self.assertIn((log["transactionHash"].lower(), 0), w2._seen)


class TestBisection(WatcherTestBase):
    def test_oversized_range_bisected_and_complete(self):
        logs = [make_log(b, 0) for b in (10, 5000, 9000)]
        rpc = FakeRpc(head=10_032, logs=logs, max_span=4000)
        fresh = self.watcher(rpc, confirmations=32).scan_once()
        self.assertEqual(len(fresh), 3)
        self.assertGreater(len(rpc.get_logs_calls), 1)

    def test_bisection_covers_every_block_exactly_once(self):
        rpc = FakeRpc(head=50_032, logs=[], max_span=1000)
        self.watcher(rpc, confirmations=32).scan_once()
        ok_calls = [c for c in rpc.get_logs_calls if c[1] - c[0] <= 1000]
        covered = []
        for frm, to in ok_calls:
            covered.extend(range(frm, to + 1))
        self.assertEqual(sorted(covered), list(range(0, 50_001)))
        self.assertEqual(len(covered), len(set(covered)))


class TestBackfill(WatcherTestBase):
    def test_backfill_archives_and_sets_cursor(self):
        rpc = FakeRpc(head=1000, logs=[make_log(1, 0), make_log(900, 0)])
        fresh = self.watcher(rpc, confirmations=32).backfill()
        self.assertEqual(len(fresh), 2)
        self.assertEqual(self.read_state()["last_scanned"], 968)

    def test_backfill_does_not_regress_cursor(self):
        rpc = FakeRpc(head=1000)
        w = self.watcher(rpc, confirmations=32)
        w.scan_once()
        w.backfill(from_block=0, to_block=500)
        self.assertEqual(self.read_state()["last_scanned"], 968)

    def test_gap_backfill_archives_but_refuses_cursor(self):
        # from_block=2000 on a fresh dir leaves [0,1999] unscanned: events
        # are archived, the cursor must NOT jump the gap.
        rpc = FakeRpc(head=5032, logs=[make_log(100, 0), make_log(3000, 0)])
        w = self.watcher(rpc, confirmations=32)
        fresh = w.backfill(from_block=2000)
        self.assertEqual(len(fresh), 1)  # block-3000 log archived
        self.assertFalse(os.path.exists(os.path.join(self.dir, "state.json")))
        # Follow-up full scan still finds the block-100 launch.
        fresh2 = w.scan_once()
        self.assertEqual([r["block"] for r in fresh2], [100])

    def test_explicit_to_block_clamped_to_confirmed_head(self):
        # A to_block beyond the head must not mark unscanned blocks covered.
        rpc = FakeRpc(head=1000, logs=[])
        w = self.watcher(rpc, confirmations=32)
        w.backfill(from_block=0, to_block=5000)
        self.assertEqual(self.read_state()["last_scanned"], 968)
        # A launch mined later inside [969, 5000] is still picked up.
        rpc.logs.append(make_log(2000, 0))
        rpc.head = 6000
        fresh = w.scan_once()
        self.assertEqual([r["block"] for r in fresh], [2000])

    def test_explicit_to_block_cannot_enter_reorg_window(self):
        rpc = FakeRpc(head=1000, logs=[make_log(990, 0)])
        w = self.watcher(rpc, confirmations=32)
        fresh = w.backfill(from_block=0, to_block=999)
        self.assertEqual(fresh, [])
        self.assertEqual(self.read_state()["last_scanned"], 968)

    def test_empty_range_after_clamp_is_noop(self):
        rpc = FakeRpc(head=100, logs=[])
        w = self.watcher(rpc, confirmations=32)
        self.assertEqual(w.backfill(from_block=90), [])


class TestDecodeResilience(WatcherTestBase):
    def test_unknown_topic_surfaced_not_dropped(self):
        # Address-only server filter means unknown topics reach the client.
        rpc = FakeRpc(head=1000, logs=[make_log(100, 0, topic0="0x" + "ee" * 32)])
        fresh = self.watcher(rpc).scan_once()
        self.assertEqual(fresh[0]["event"], "Unknown")

    def test_malformed_payload_becomes_decode_failed_record(self):
        # Known topic, garbage data: must surface as DecodeFailed and let
        # the scan continue — not stall the pipeline forever.
        bad = make_log(100, 0, topic0=TOPIC_INITIALIZER_CREATED, data="0x1234")
        ok = make_log(200, 0)
        rpc = FakeRpc(head=1000, logs=[bad, ok])
        fresh = self.watcher(rpc).scan_once()
        self.assertEqual([r["event"] for r in fresh],
                         ["DecodeFailed", "TokenCreated"])
        self.assertIn("error", fresh[0])
        self.assertEqual(self.read_state()["last_scanned"], 968)

    def test_migration_failed_decoded(self):
        log = make_log(100, 0, topic0=TOPIC_MIGRATION_FAILED,
                       data="0x" + ("%064x" % 32) + ("%064x" % 4)
                            + "deadbeef" + "00" * 28)
        rpc = FakeRpc(head=1000, logs=[log])
        fresh = self.watcher(rpc).scan_once()
        self.assertEqual(fresh[0]["event"], "MigrationFailed")
        self.assertEqual(fresh[0]["reason"], "0xdeadbeef")


class TestArchiveResilience(WatcherTestBase):
    def test_torn_final_line_tolerated_and_rescanned(self):
        log = make_log(100, 0)
        rpc = FakeRpc(head=1000, logs=[log])
        w = self.watcher(rpc)
        w.scan_once()
        # Simulate a crash mid-append: truncate the final line.
        path = os.path.join(self.dir, "events.jsonl")
        with open(path) as f:
            content = f.read()
        with open(path, "w") as f:
            f.write(content[:len(content) // 2])
        os.unlink(os.path.join(self.dir, "state.json"))
        w2 = self.watcher(rpc)  # must not raise; torn tail truncated away
        fresh = w2.scan_once()  # cursor was not advanced → rescan re-archives
        self.assertEqual(len(fresh), 1)
        archive = self.read_archive()  # parses cleanly: no torn line left
        self.assertEqual(len(archive), 1)
        self.assertEqual(archive[-1]["block"], 100)
        # A further restart is also clean and remembers the record.
        w3 = self.watcher(rpc)
        self.assertIn((log["transactionHash"].lower(), 0), w3._seen)

    def test_torn_middle_line_raises(self):
        log = make_log(100, 0)
        rpc = FakeRpc(head=1000, logs=[log])
        self.watcher(rpc).scan_once()
        path = os.path.join(self.dir, "events.jsonl")
        with open(path, "a") as f:
            f.write('{"broken\n')
            f.write(json.dumps({"tx": "0x1", "log_index": 1}) + "\n")
        with self.assertRaises(json.JSONDecodeError):
            self.watcher(rpc)


if __name__ == "__main__":
    unittest.main()
