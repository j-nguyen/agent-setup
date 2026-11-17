import unittest

from app.router import dispatch
from app.storage import customers_repo, db, orders_repo


class OrdersTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect()
        self.customer = customers_repo.insert(self.conn, "Ada")

    def test_get_order(self):
        order_id = orders_repo.insert(self.conn, self.customer, 1250, "paid", "2026-01-02T10:00:00Z")
        status, body = dispatch(self.conn, "GET", f"/orders/{order_id}")
        self.assertEqual(status, 200)
        self.assertEqual(body["total_cents"], 1250)

    def test_missing_order_is_404(self):
        status, _ = dispatch(self.conn, "GET", "/orders/999")
        self.assertEqual(status, 404)

    def test_bad_id_is_400(self):
        status, _ = dispatch(self.conn, "GET", "/orders/abc")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
