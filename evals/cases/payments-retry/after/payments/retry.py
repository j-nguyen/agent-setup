"""Backoff schedule for retrying transient provider failures."""
from __future__ import annotations

import random
from collections.abc import Iterator


def backoff_delays(attempts: int, base: float = 0.5, cap: float = 8.0) -> Iterator[float]:
    """Yield one delay (seconds) per attempt: exponential, capped, with "equal jitter".

    The delay yielded with the last attempt is never slept on.
    """
    for n in range(attempts):
        delay = min(cap, base * 2 ** n)
        yield delay / 2 + random.uniform(0, delay / 2)
