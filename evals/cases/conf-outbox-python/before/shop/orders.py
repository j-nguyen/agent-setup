"""Order creation."""
import sqlite3


class InvalidOrder(ValueError):
    pass


def _validate(items: list[dict]) -> None:
    if not items:
        raise InvalidOrder("an order needs at least one item")
    for item in items:
        if item["qty"] <= 0:
            raise InvalidOrder(f"bad quantity for {item['sku']}")


def create_order(conn: sqlite3.Connection, customer_id: int, items: list[dict]) -> int:
    """Create an order and its items atomically. Returns the order id."""
    _validate(items)
    total = sum(i["qty"] * i["price_cents"] for i in items)
    with conn:  # one transaction: commit on success, roll back on error
        cur = conn.execute(
            "INSERT INTO orders (customer_id, total_cents) VALUES (?, ?)",
            (customer_id, total),
        )
        order_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO order_items (order_id, sku, qty, price_cents) VALUES (?, ?, ?, ?)",
            [(order_id, i["sku"], i["qty"], i["price_cents"]) for i in items],
        )
    return order_id
