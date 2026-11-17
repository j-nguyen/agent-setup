import sqlite3


def get(conn: sqlite3.Connection, customer_id: int):
    return conn.execute("SELECT id, name FROM customers WHERE id = ?", (customer_id,)).fetchone()


def insert(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("INSERT INTO customers (name) VALUES (?)", (name,))
    return cur.lastrowid
