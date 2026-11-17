import unittest

from shop.db import connect
from shop.orders import InvalidOrder, create_order
from tests.helpers import make_broker

ITEMS = [{"sku": "A1", "qty": 2, "price_cents": 500}, {"sku": "B2", "qty": 1, "price_cents": 250}]


class CreateOrderTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()

    def test_creates_order_with_total(self):
        oid = create_order(self.conn, 7, ITEMS)
        row = self.conn.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
        self.assertEqual(row["total_cents"], 1250)

    def test_rejects_empty_order(self):
        with self.assertRaises(InvalidOrder):
            create_order(self.conn, 7, [])

    def test_committed_order_has_one_outbox_row(self):
        create_order(self.conn, 7, ITEMS)
        rows = self.conn.execute("SELECT topic FROM outbox_events").fetchall()
        self.assertEqual([r["topic"] for r in rows], ["order.created"])

    def test_rolled_back_order_leaves_no_outbox_row(self):
        bad = ITEMS + [{"sku": "C3", "qty": 1, "price_cents": -1}]  # violates the CHECK constraint
        with self.assertRaises(Exception):
            create_order(self.conn, 7, bad)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0], 0)

    def test_publishes_immediately_when_broker_given(self):
        broker, transport = make_broker()
        create_order(self.conn, 7, ITEMS, broker=broker)
        self.assertEqual(len(transport.sent), 1)
        unsent = self.conn.execute("SELECT COUNT(*) FROM outbox_events WHERE sent_at IS NULL").fetchone()[0]
        self.assertEqual(unsent, 0)


if __name__ == "__main__":
    unittest.main()
