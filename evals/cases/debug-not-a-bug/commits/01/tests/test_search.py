import unittest

from catalog.search import search_products

PRODUCTS = [
    {"name": "iPhone 15", "code": "SKU-aB12"},
    {"name": "iPhone 15 Case", "code": "SKU-Ab12"},
]


class SearchTest(unittest.TestCase):
    def test_default_is_case_sensitive_by_design(self):
        self.assertEqual(search_products(PRODUCTS, "iphone"), [])
        self.assertEqual([p["code"] for p in search_products(PRODUCTS, "SKU-aB12")], ["SKU-aB12"])

    def test_ignore_case_option(self):
        self.assertEqual(len(search_products(PRODUCTS, "iphone", case_sensitive=False)), 2)


if __name__ == "__main__":
    unittest.main()
