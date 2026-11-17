import unittest

from accounts import models
from billing.invoices import create_invoice
from core import db
from jobs import worker
from tests.base import DbTestCase


class InvoiceTest(DbTestCase):
    def test_pdf_rendered_in_background(self):
        with db.atomic():
            user = models.create_user("x@example.com", "X", "pw-long-enough")
        inv = create_invoice(user.id, 1200)
        self.assertIsNone(db.execute("SELECT pdf_path FROM invoices WHERE id=?", (inv,)).fetchone()["pdf_path"])
        worker.run_once()
        self.assertTrue(db.execute("SELECT pdf_path FROM invoices WHERE id=?", (inv,)).fetchone()["pdf_path"])


if __name__ == "__main__":
    unittest.main()
