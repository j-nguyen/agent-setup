"""Postgres access via a psycopg 3 pool. Always pass values as %s parameters."""
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool = ConnectionPool(kwargs={"row_factory": dict_row}, open=False)


def query(sql: str, params=()) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


@contextmanager
def transaction():
    """One connection, one transaction: commits on success, rolls back on error."""
    with pool.connection() as conn, conn.transaction():
        yield conn
