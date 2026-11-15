"""Run a unit of work in its own transaction, retrying the whole thing on conflicts."""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import OperationalError

T = TypeVar("T")

# serialization_failure, deadlock_detected
RETRYABLE_SQLSTATES = {"40001", "40P01"}


def run_in_transaction(Session, work: Callable[..., T], *, attempts: int = 3, sleep=time.sleep) -> T:
    """Call work(session) inside `Session.begin()`; commit on success, roll back on error.

    The whole unit (reads included) is re-run on a serialization failure or deadlock,
    so `work` must decide everything from what it reads inside the transaction.
    """
    for attempt in range(1, attempts + 1):
        try:
            with Session.begin() as session:
                return work(session)
        except OperationalError as e:
            sqlstate = getattr(e.orig, "sqlstate", None)
            if sqlstate not in RETRYABLE_SQLSTATES or attempt == attempts:
                raise
            sleep(0.02 * 2 ** attempt * random.uniform(0.5, 1.5))
    raise AssertionError("unreachable")
