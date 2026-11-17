import sqlite3


def get(conn: sqlite3.Connection, order_id: int):
    return conn.execute(
        "SELECT id, customer_id, total_cents, status, created_at FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()


def list_for_customer(conn: sqlite3.Connection, customer_id: int) -> list:
    return conn.execute(
        "SELECT id, customer_id, total_cents, status, created_at FROM orders "
        "WHERE customer_id = ? ORDER BY created_at",
        (customer_id,),
    ).fetchall()


def insert(conn: sqlite3.Connection, customer_id: int, total_cents: int, status: str, created_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO orders (customer_id, total_cents, status, created_at) VALUES (?, ?, ?, ?)",
        (customer_id, total_cents, status, created_at),
    )
    return cur.lastrowid


def summarize_for_customer(conn: sqlite3.Connection, customer_id: int):
    return conn.execute(
        "SELECT COUNT(*) AS order_count, COALESCE(SUM(total_cents), 0) AS total_cents, "
        "MAX(created_at) AS last_order_at FROM orders WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()


def list_recent_for_customer(conn: sqlite3.Connection, customer_id: int, limit: int) -> list:
    return conn.execute(
        "SELECT id, total_cents, status, created_at FROM orders "
        "WHERE customer_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (customer_id, limit),
    ).fetchall()
