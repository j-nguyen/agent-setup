import unittest

from tests.helpers import FREE_KEY, get, setup_app


class RequireApiKeyTest(unittest.TestCase):
    def setUp(self):
        self.app, _ = setup_app()

    def test_missing_key_is_401(self):
        r = get(self.app, "/v1/products")
        self.assertEqual(r.status, 401)
        self.assertEqual(r.json()["error"]["code"], "invalid_api_key")

    def test_wrong_key_is_401(self):
        self.assertEqual(get(self.app, "/v1/products", key="nope").status, 401)

    def test_valid_key_passes(self):
        self.assertEqual(get(self.app, "/v1/products", key=FREE_KEY).status, 200)

    def test_status_needs_no_key(self):
        self.assertEqual(get(self.app, "/v1/status").status, 200)


if __name__ == "__main__":
    unittest.main()
