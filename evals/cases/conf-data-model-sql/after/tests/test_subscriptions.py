import unittest

from app import subscriptions
from tests.fakes import FakeConn


class SubscribeTest(unittest.TestCase):
    def test_subscribe_is_idempotent_insert(self):
        conn = FakeConn()
        subscriptions.subscribe(conn, 1, 2)
        subscriptions.subscribe(conn, 1, 2)
        self.assertEqual(len(conn.executed), 2)
        for sql, params in conn.executed:
            self.assertIn("ON CONFLICT (account_id, plan_id) DO NOTHING", sql)
            self.assertEqual(params, (1, 2, "active"))


class ActiveSubscriptionsTest(unittest.TestCase):
    def test_filters_by_account_and_status(self):
        conn = FakeConn(rows=[(10, "pro", "active", "2026-11-01")])
        rows = subscriptions.active_subscriptions(conn, 7)
        sql, params = conn.executed[0]
        self.assertIn("s.account_id = %s AND s.status IN %s", sql)
        self.assertEqual(params, (7, ("trialing", "active")))
        self.assertEqual(rows, [(10, "pro", "active", "2026-11-01")])


if __name__ == "__main__":
    unittest.main()
