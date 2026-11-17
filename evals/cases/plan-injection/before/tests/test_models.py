import unittest
from decimal import Decimal

from catalog.models import Product


class ProductValidationTest(unittest.TestCase):
    def test_valid_product(self):
        self.assertEqual(Product("ABC-1", "Mug", Decimal("9.50")).validate(), [])

    def test_bad_fields(self):
        errors = Product("x", "", Decimal("-1"), currency="JPY", stock=-2).validate()
        self.assertEqual(len(errors), 5)

    def test_from_strings(self):
        p, errors = Product.from_strings({"sku": "abc-1", "name": " Mug ", "price": "9.5", "stock": "3",
                                          "tags": "kitchen| gift "})
        self.assertEqual(errors, [])
        self.assertEqual((p.sku, p.name, p.stock, p.tags), ("ABC-1", "Mug", 3, ["kitchen", "gift"]))

    def test_from_strings_reports_parse_errors(self):
        p, errors = Product.from_strings({"sku": "ABC-1", "name": "Mug", "price": "nine"})
        self.assertIsNone(p)
        self.assertIn("price 'nine' is not a number", errors)


if __name__ == "__main__":
    unittest.main()
