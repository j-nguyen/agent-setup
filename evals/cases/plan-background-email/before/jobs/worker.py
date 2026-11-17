"""Runs due jobs. `python -m jobs.worker` loops forever; tests call run_once()."""
from __future__ import annotations

import json
import logging
import time

from core import db
from jobs.handlers import HANDLERS

log = logging.getLogger(__name__)
BACKOFF_BASE_SECONDS = 30  # 30s, 60s, 120s, 240s, ...


def backoff(attempts: int) -> float:
    return BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))


def _claim(now: float):
    with db.atomic():
        row = db.execute(
            "SELECT * FROM jobs WHERE status = 'queued' AND run_at <= ? ORDER BY run_at LIMIT 1",
            (now,),
        ).fetchone()
        if row is None:
            return None
        # Postgres: SELECT ... FOR UPDATE SKIP LOCKED; SQLite serializes writers anyway.
        db.execute("UPDATE jobs SET status = 'running', attempts = attempts + 1 WHERE id = ?", (row["id"],))
        return dict(row) | {"attempts": row["attempts"] + 1}


def run_once(now: float | None = None) -> bool:
    """Run one due job. Returns False if there was nothing to do."""
    now = time.time() if now is None else now
    job = _claim(now)
    if job is None:
        return False
    fn = HANDLERS.get(job["kind"])
    try:
        if fn is None:
            raise LookupError(f"no handler for {job['kind']}")
        fn(json.loads(job["payload"]))
    except Exception as exc:
        dead = job["attempts"] >= job["max_attempts"]
        log.warning("job %s (%s) failed on attempt %s: %s", job["id"], job["kind"], job["attempts"], exc)
        db.execute("UPDATE jobs SET status = ?, run_at = ?, last_error = ? WHERE id = ?",
                   ("dead" if dead else "queued", now + backoff(job["attempts"]), repr(exc), job["id"]))
        return True
    db.execute("UPDATE jobs SET status = 'done', last_error = NULL WHERE id = ?", (job["id"],))
    return True


def main() -> None:  # pragma: no cover
    import billing.invoices  # noqa: F401  (registers handlers)
    db.connect("shopfront.db")
    while True:
        if not run_once():
            time.sleep(1)


if __name__ == "__main__":  # pragma: no cover
    main()
