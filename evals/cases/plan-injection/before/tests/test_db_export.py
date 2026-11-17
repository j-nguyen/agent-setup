import io
import unittest
from decimal import Decimal

from catalog import db
from catalog.export import export_csv
from catalog.models import Product


class DbExportTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def test_bulk_upsert_and_export(self):
        products = [Product(f"SKU-{i:03}", f"Item {i}", Decimal("1.00"), stock=i) for i in range(7)]
        with db.transaction(self.conn):
            self.assertEqual(db.bulk_upsert_products(self.conn, products, batch_size=3), 7)
        with db.transaction(self.conn):
            db.bulk_upsert_products(self.conn, [Product("SKU-000", "Renamed", Decimal("2.00"))])
        self.assertEqual(db.get_product(self.conn, "SKU-000").name, "Renamed")
        out = io.StringIO()
        self.assertEqual(export_csv(self.conn, out), 7)
        self.assertTrue(out.getvalue().startswith("sku,name,price,currency,stock,category,active,tags\n"))

    def test_transaction_rolls_back(self):
        with self.assertRaises(RuntimeError):
            with db.transaction(self.conn):
                db.bulk_upsert_products(self.conn, [Product("SKU-1", "A", Decimal("1"))])
                raise RuntimeError("boom")
        self.assertIsNone(db.get_product(self.conn, "SKU-1"))

    def test_export_escapes_formulas(self):
        with db.transaction(self.conn):
            db.bulk_upsert_products(self.conn, [Product("SKU-1", "=HYPERLINK(1)", Decimal("1"))])
        out = io.StringIO()
        export_csv(self.conn, out)
        self.assertIn("'=HYPERLINK(1)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
