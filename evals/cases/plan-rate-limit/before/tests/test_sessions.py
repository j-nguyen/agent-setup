import json
import unittest

from app.http import Request
from tests.helpers import setup_app


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.app, self.redis = setup_app()

    def _login(self):
        body = json.dumps({"email": "ana@example.com", "password": "correct horse"}).encode()
        return self.app.dispatch(Request("POST", "/dashboard/login", {}, {}, body))

    def test_login_then_me(self):
        cookie = self._login().headers["Set-Cookie"].split(";")[0]
        r = self.app.dispatch(Request("GET", "/dashboard/me", {"cookie": cookie}))
        self.assertEqual(r.json()["email"], "ana@example.com")

    def test_redis_down_is_503(self):
        cookie = self._login().headers["Set-Cookie"].split(";")[0]
        self.redis.down = True
        r = self.app.dispatch(Request("GET", "/dashboard/me", {"cookie": cookie}))
        self.assertEqual(r.status, 503)


if __name__ == "__main__":
    unittest.main()
