import unittest

from app.router import dispatch
from app.storage import customers_repo, db, orders_repo


class CustomerSummaryTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect()
        self.ada = customers_repo.insert(self.conn, "Ada")
        self.bob = customers_repo.insert(self.conn, "Bob")
        orders_repo.insert(self.conn, self.ada, 1000, "paid", "2026-01-01T09:00:00Z")
        orders_repo.insert(self.conn, self.ada, 2500, "paid", "2026-01-03T09:00:00Z")
        orders_repo.insert(self.conn, self.ada, 700, "refunded", "2026-01-02T09:00:00Z")

    def test_summary(self):
        status, body = dispatch(self.conn, "GET", f"/customers/{self.ada}/summary")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"customer_id": self.ada, "order_count": 3, "total_cents": 4200,
                                "last_order_at": "2026-01-03T09:00:00Z"})

    def test_summary_without_orders(self):
        status, body = dispatch(self.conn, "GET", f"/customers/{self.bob}/summary")
        self.assertEqual(status, 200)
        self.assertEqual(body["order_count"], 0)
        self.assertEqual(body["total_cents"], 0)
        self.assertIsNone(body["last_order_at"])

    def test_unknown_customer_is_404(self):
        self.assertEqual(dispatch(self.conn, "GET", "/customers/999/summary")[0], 404)
        self.assertEqual(dispatch(self.conn, "GET", "/customers/999/orders/recent")[0], 404)


class RecentOrdersTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect()
        self.ada = customers_repo.insert(self.conn, "Ada")
        for day in range(1, 61):
            orders_repo.insert(self.conn, self.ada, day * 100, "paid", f"2026-03-{day % 28 + 1:02d}T{day % 24:02d}:00:00Z")

    def test_newest_first_with_default_limit(self):
        status, body = dispatch(self.conn, "GET", f"/customers/{self.ada}/orders/recent")
        self.assertEqual(status, 200)
        created = [o["created_at"] for o in body["items"]]
        self.assertEqual(len(created), 5)
        self.assertEqual(created, sorted(created, reverse=True))

    def test_limit_is_capped(self):
        _, body = dispatch(self.conn, "GET", f"/customers/{self.ada}/orders/recent", {"limit": "500"})
        self.assertEqual(len(body["items"]), 50)

    def test_bad_limit_is_400(self):
        status, _ = dispatch(self.conn, "GET", f"/customers/{self.ada}/orders/recent", {"limit": "lots"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
