"""An exclusive lock held on the resource, not on the caller.

refresh.sh already guards itself with a pid file, which stops two scheduled
runs from overlapping. It does not stop a scheduled run from overlapping a
manual one, because a person typing `python3 scripts/build_feed.py` never
touches that pid file — and the script's own header promises it is safe to
run by hand. It was not: a hand-run rebuild and a launchd rebuild both held
the feed cache in memory and the slower one wrote last, silently discarding
the other's work.

Locking the cache file itself fixes every caller at once, including ones
that do not exist yet.
"""

import errno
import fcntl
import os
from contextlib import contextmanager


class Locked(Exception):
    """Another process holds the lock. The caller must not proceed —
    two writers to the same cache means one of them loses silently."""


@contextmanager
def exclusive(path: str, what: str = "this resource"):
    """Hold an exclusive, non-blocking lock for the duration of the block.

    Non-blocking on purpose. Waiting would make a manual run appear hung
    behind a thirty-minute rebuild; failing tells the operator what is
    happening and lets them decide.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            holder = ""
            try:
                holder = os.read(fd, 32).decode().strip()
            except OSError:
                pass
            raise Locked(
                "another process%s is already writing %s. Wait for it to "
                "finish, or stop it first (scheduled refresh: "
                "`launchctl unload ~/Library/LaunchAgents/"
                "xyz.gavelscan.refresh.plist`)."
                % (" (pid %s)" % holder if holder else "", what))
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        os.fsync(fd)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
