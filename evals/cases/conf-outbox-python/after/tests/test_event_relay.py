import unittest

from shop.db import connect
from shop.event_relay import relay_pending
from shop.orders import create_order
from tests.helpers import make_broker

ITEMS = [{"sku": "A1", "qty": 1, "price_cents": 100}]


class RelayTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()

    def test_publishes_pending_in_order_and_marks_sent(self):
        a = create_order(self.conn, 1, ITEMS)
        b = create_order(self.conn, 2, ITEMS)
        broker, transport = make_broker()
        self.assertEqual(relay_pending(self.conn, broker), 2)
        order_ids = [body for _, body in transport.sent]
        self.assertIn(f'"order_id": {a}', order_ids[0])
        self.assertIn(f'"order_id": {b}', order_ids[1])
        self.assertEqual(relay_pending(self.conn, broker), 0)

    def test_failure_leaves_row_unsent(self):
        create_order(self.conn, 1, ITEMS)
        broker, transport = make_broker(fail_times=1)
        self.assertEqual(relay_pending(self.conn, broker), 0)
        unsent = self.conn.execute("SELECT COUNT(*) FROM outbox_events WHERE sent_at IS NULL").fetchone()[0]
        self.assertEqual(unsent, 1)

    def test_batch_size_limits_a_run(self):
        for _ in range(3):
            create_order(self.conn, 1, ITEMS)
        broker, _ = make_broker()
        self.assertEqual(relay_pending(self.conn, broker, batch_size=2), 2)


if __name__ == "__main__":
    unittest.main()
