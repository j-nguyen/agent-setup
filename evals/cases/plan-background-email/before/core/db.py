"""Database connection, transactions and on-commit hooks."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

_local = threading.local()
_conn: sqlite3.Connection | None = None
MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def connect(dsn: str = ":memory:") -> sqlite3.Connection:
    """Open the connection (Postgres via the same API in production) and migrate."""
    global _conn
    _conn = sqlite3.connect(dsn, isolation_level=None, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    for f in sorted(MIGRATIONS.glob("*.sql")):
        _conn.executescript(f.read_text())
    _local.depth = 0
    _local.callbacks = []
    return _conn


def conn() -> sqlite3.Connection:
    assert _conn is not None, "call db.connect() first"
    return _conn


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    return conn().execute(sql, params)


def _state():
    if not hasattr(_local, "depth"):
        _local.depth, _local.callbacks = 0, []
    return _local


@contextmanager
def atomic():
    """A transaction; nested calls use savepoints. Commits on success, rolls back on error."""
    st = _state()
    c = conn()
    if st.depth == 0:
        c.execute("BEGIN")
    else:
        c.execute(f"SAVEPOINT sp{st.depth}")
    st.depth += 1
    try:
        yield c
    except BaseException:
        st.depth -= 1
        if st.depth == 0:
            c.execute("ROLLBACK")
            st.callbacks = []
        else:
            c.execute(f"ROLLBACK TO SAVEPOINT sp{st.depth}")
            c.execute(f"RELEASE SAVEPOINT sp{st.depth}")
        raise
    st.depth -= 1
    if st.depth == 0:
        c.execute("COMMIT")
        callbacks, st.callbacks = st.callbacks, []
        for fn in callbacks:
            fn()
    else:
        c.execute(f"RELEASE SAVEPOINT sp{st.depth}")


def on_commit(fn: Callable[[], None]) -> None:
    """Run fn after the outermost transaction commits (immediately if none is open).
    Dropped if the transaction rolls back."""
    st = _state()
    if st.depth == 0:
        fn()
    else:
        st.callbacks.append(fn)
