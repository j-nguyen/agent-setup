import unittest

from tests.helpers import PRO_KEY, get, setup_app


class PublicApiTest(unittest.TestCase):
    def setUp(self):
        self.app, _ = setup_app()

    def test_list_filters_by_category(self):
        r = get(self.app, "/v1/products?category=office", key=PRO_KEY)
        self.assertEqual([p["id"] for p in r.json()["items"]], ["p2", "p3"])

    def test_get_one(self):
        self.assertEqual(get(self.app, "/v1/products/p1", key=PRO_KEY).json()["name"], "Desk lamp")

    def test_unknown_product_is_404(self):
        self.assertEqual(get(self.app, "/v1/products/zzz", key=PRO_KEY).status, 404)

    def test_request_id_echoed(self):
        r = get(self.app, "/v1/products", key=PRO_KEY, x_request_id="abc")
        self.assertEqual(r.headers["X-Request-Id"], "abc")


if __name__ == "__main__":
    unittest.main()
