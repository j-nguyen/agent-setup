import csv
import io
import unittest

import app.routes.admin  # noqa: F401  registers routes
from app import audit, store
from app.web import Request, User, router

ADMIN = User(1, frozenset({"admin"}))


class ExportTest(unittest.TestCase):
    def setUp(self):
        audit.EVENTS.clear()
        store.CUSTOMERS[:] = [
            store.Customer(2, "=HYPERLINK(\"http://x\")", "b@example.com", "2026-02-01", "hash2", "vip"),
            store.Customer(1, "Ada", "ada@example.com", "2026-01-01", "hash1"),
        ]

    def export(self, user=ADMIN):
        return router.dispatch(Request("GET", "/admin/customers/export", user))

    def test_columns_and_order(self):
        rows = list(csv.reader(io.StringIO(self.export().body)))
        self.assertEqual(rows[0], ["id", "name", "email", "created_at"])
        self.assertEqual([r[0] for r in rows[1:]], ["1", "2"])
        self.assertNotIn("hash1", self.export().body)

    def test_formula_cells_escaped(self):
        rows = list(csv.reader(io.StringIO(self.export().body)))
        self.assertTrue(rows[2][1].startswith("'="))

    def test_audit_event(self):
        self.export()
        self.assertEqual(audit.EVENTS[-1], {"actor": 1, "action": "customers.export", "detail": {"rows": 2}})


if __name__ == "__main__":
    unittest.main()
