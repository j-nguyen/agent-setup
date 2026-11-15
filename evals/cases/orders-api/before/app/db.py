"""Thin database helpers. Always pass values through `params`; never format them into SQL."""
import os

import psycopg
from psycopg.rows import dict_row

_DSN = os.environ["DATABASE_URL"]


def query(sql: str, params: list | tuple = ()) -> list[dict]:
    with psycopg.connect(_DSN, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: list | tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None
