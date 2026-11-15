"""SQLite access. Always pass values as `?` parameters; never format them into SQL."""
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA.read_text())
    return conn
