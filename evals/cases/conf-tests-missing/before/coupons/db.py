import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def connect(path: str = ":memory:") -> sqlite3.Connection:
    # Autocommit mode: callers that need a transaction open it explicitly with BEGIN.
    conn = sqlite3.connect(path, timeout=5, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    for f in sorted(MIGRATIONS.glob("*.sql")):
        conn.executescript(f.read_text())
