"""Order creation."""
import json
import sqlite3

from shop.broker import Broker, PublishError

ORDER_CREATED = "order.created"


class InvalidOrder(ValueError):
    pass


def _validate(items: list[dict]) -> None:
    if not items:
        raise InvalidOrder("an order needs at least one item")
    for item in items:
        if item["qty"] <= 0:
            raise InvalidOrder(f"bad quantity for {item['sku']}")


def create_order(conn: sqlite3.Connection, customer_id: int, items: list[dict],
                 broker: Broker | None = None) -> int:
    """Create an order and its items atomically. Returns the order id.

    The order.created event is recorded in the outbox. When a broker is passed,
    the event is also published right away so consumers see it without waiting
    for the next relay run; the relay picks up anything that didn't go out.
    """
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
        payload = {"order_id": order_id, "customer_id": customer_id, "total_cents": total}
        sent_at = None
        if broker is not None:
            try:
                broker.publish(ORDER_CREATED, payload)
                sent_at = conn.execute("SELECT datetime('now')").fetchone()[0]
            except PublishError:
                pass  # the relay will retry it
        conn.execute(
            "INSERT INTO outbox_events (topic, payload, sent_at) VALUES (?, ?, ?)",
            (ORDER_CREATED, json.dumps(payload, sort_keys=True), sent_at),
        )
    return order_id
