import unittest

import app.routes.customers  # noqa: F401  registers routes
from app import store
from app.web import Request, User, router


class ShowCustomerTest(unittest.TestCase):
    def setUp(self):
        store.CUSTOMERS[:] = [store.Customer(1, "Ada", "ada@example.com", "2026-01-01", "x")]

    def test_requires_support_role(self):
        r = router.dispatch(Request("GET", "/customers/one", User(5), {"id": "1"}))
        self.assertEqual(r.status, 403)

    def test_shows_customer(self):
        r = router.dispatch(Request("GET", "/customers/one", User(5, frozenset({"support"})), {"id": "1"}))
        self.assertEqual(r.status, 200)


if __name__ == "__main__":
    unittest.main()
