import unittest

from shop.db import connect
from shop.orders import InvalidOrder, create_order

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


if __name__ == "__main__":
    unittest.main()
