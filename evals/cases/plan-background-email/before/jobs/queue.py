"""Enqueue background jobs into the `jobs` table."""
from __future__ import annotations

import json
import sqlite3
import time

from core import db


def enqueue(kind: str, payload: dict, *, dedupe_key: str | None = None,
            delay_seconds: float = 0, max_attempts: int = 5) -> int | None:
    """Insert a job. Runs in the caller's transaction if one is open, so the job
    only exists if that transaction commits.

    With a dedupe_key, a second enqueue with the same key is ignored and returns None.
    """
    try:
        cur = db.execute(
            "INSERT INTO jobs (kind, payload, run_at, max_attempts, dedupe_key) VALUES (?, ?, ?, ?, ?)",
            (kind, json.dumps(payload), time.time() + delay_seconds, max_attempts, dedupe_key),
        )
    except sqlite3.IntegrityError:
        if dedupe_key is None:
            raise
        return None
    return cur.lastrowid


def get(job_id: int) -> dict | None:
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None
