import hashlib
import hmac
import json
import unittest

from hooks import ledger, receiver, signature
from hooks.config import WEBHOOK_SECRET
from hooks.dedupe import SeenEvents


def sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()


class SignatureTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(signature.verify(b"{}", sign(b"{}")))

    def test_tampered(self):
        self.assertFalse(signature.verify(b'{"a":1}', sign(b"{}")))

    def test_missing(self):
        self.assertFalse(signature.verify(b"{}", None))


class LedgerTest(unittest.TestCase):
    def test_retries_then_succeeds(self):
        responses = iter([503, 200])
        sleeps = []
        status = ledger.forward(b"{}", send=lambda url, body: next(responses), sleep=sleeps.append)
        self.assertEqual(status, 200)
        self.assertEqual(len(sleeps), 1)

    def test_gives_up_after_five(self):
        calls = []
        with self.assertRaises(ledger.LedgerUnavailable):
            ledger.forward(b"{}", send=lambda url, body: calls.append(1) or 503, sleep=lambda s: None)
        self.assertEqual(len(calls), 5)


class ReceiverTest(unittest.TestCase):
    def setUp(self):
        receiver.seen = SeenEvents()
        self.forwarded = []

    def call(self, body: bytes, sig: str | None):
        return receiver.handle(body, {"X-Signature": sig} if sig else {}, forward=self.forwarded.append)

    def test_forwards_once(self):
        body = json.dumps({"id": "evt_1", "type": "charge.succeeded"}).encode()
        self.assertEqual(self.call(body, sign(body)), 200)
        self.assertEqual(self.call(body, sign(body)), 200)
        self.assertEqual(len(self.forwarded), 1)

    def test_rejects_forged(self):
        body = json.dumps({"id": "evt_2"}).encode()
        self.assertEqual(self.call(body, "deadbeef"), 401)
        self.assertEqual(self.forwarded, [])


if __name__ == "__main__":
    unittest.main()
