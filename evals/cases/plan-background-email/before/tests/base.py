import unittest

from core import db
from emails import sender


class FakeTransport:
    def __init__(self):
        self.sent = []
        self.fail_next = 0

    def send(self, msg):
        if self.fail_next:
            self.fail_next -= 1
            raise OSError("smtp timeout")
        self.sent.append(msg)


class DbTestCase(unittest.TestCase):
    def setUp(self):
        db.connect(":memory:")
        self.mail = FakeTransport()
        self._orig = sender.transport
        sender.transport = self.mail

    def tearDown(self):
        sender.transport = self._orig
