"""Small retry helper for transient backend failures (PRD 23/24 robustness)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def with_retries(
    fn: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Call `fn`, retrying on `exceptions` with exponential backoff."""
    last: BaseException | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except exceptions as exc:  # noqa: BLE001 - deliberate breadth, caller scopes it
            last = exc
            if attempt >= attempts:
                break
            if on_retry:
                on_retry(attempt, exc)
            time.sleep(base_delay * (2 ** (attempt - 1)))
    assert last is not None
    raise last
