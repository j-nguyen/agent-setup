"""Publishes outbox events to the broker."""
import json
import sqlite3

from shop.broker import Broker, PublishError


def relay_pending(conn: sqlite3.Connection, broker: Broker, batch_size: int = 100) -> int:
    """Publish up to `batch_size` unsent events in id order. Returns how many were sent."""
    rows = conn.execute(
        "SELECT id, topic, payload FROM outbox_events WHERE sent_at IS NULL ORDER BY id LIMIT ?",
        (batch_size,),
    ).fetchall()
    sent = 0
    for row in rows:
        try:
            broker.publish(row["topic"], json.loads(row["payload"]))
        except PublishError:
            break  # leave this and later rows for the next run
        with conn:
            conn.execute("UPDATE outbox_events SET sent_at = datetime('now') WHERE id = ?", (row["id"],))
        sent += 1
    return sent


def replay_events(conn: sqlite3.Connection, broker: Broker, since_id: int = 0) -> int:
    """Re-publish every event with id > since_id, sent or not. Used by `shop.admin replay`."""
    rows = conn.execute(
        "SELECT id, topic, payload FROM outbox_events WHERE id > ? ORDER BY id", (since_id,)
    ).fetchall()
    for row in rows:
        broker.publish(row["topic"], json.loads(row["payload"]))
    with conn:
        conn.execute("UPDATE outbox_events SET sent_at = datetime('now') WHERE id > ?", (since_id,))
    return len(rows)
