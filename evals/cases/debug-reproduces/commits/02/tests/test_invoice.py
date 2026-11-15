import unittest
from decimal import Decimal

from billing.invoice import LineItem, invoice_total


class InvoiceTest(unittest.TestCase):
    def test_sums_lines(self):
        items = [LineItem("a", Decimal("10.00"), 2), LineItem("b", Decimal("5.50"), 1)]
        self.assertEqual(invoice_total(items), Decimal("25.50"))

    def test_discount_single_item(self):
        items = [LineItem("a", Decimal("50.00"), 1)]
        self.assertEqual(invoice_total(items, Decimal("10")), Decimal("45.00"))


if __name__ == "__main__":
    unittest.main()
