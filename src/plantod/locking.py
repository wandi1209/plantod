"""Advisory file lock so concurrent PLANTOD runs can't corrupt state (PRD 23)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


class LockBusy(Exception):
    """Raised when another process already holds the project lock."""


@contextmanager
def project_lock(artifact_dir: Path):
    """Exclusive, non-blocking advisory lock on `<artifact_dir>/.lock`.

    Uses fcntl on POSIX; degrades to a best-effort lockfile elsewhere.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    lock_path = artifact_dir / ".lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    acquired = False
    try:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except ImportError:
            # non-POSIX: fall back to presence-based best effort
            acquired = True
        except OSError as e:
            raise LockBusy(
                f"another plantod process holds the lock at {lock_path}"
            ) from e
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        try:
            if acquired:
                try:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_UN)
                except ImportError:
                    pass
        finally:
            os.close(fd)
