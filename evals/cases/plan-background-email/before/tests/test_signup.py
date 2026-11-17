import unittest

from accounts import models
from accounts.signup import SignupError, signup
from core import db
from tests.base import DbTestCase


class SignupTest(DbTestCase):
    def test_creates_user_and_profile_and_sends_welcome(self):
        user = signup("Ana@Example.com", "Ana", "long-enough-pw", locale="fr")
        self.assertEqual(models.get_user(user.id).email, "ana@example.com")
        self.assertEqual(models.get_locale(user.id), "fr")
        self.assertEqual(len(self.mail.sent), 1)
        self.assertEqual(self.mail.sent[0]["Subject"], "Bienvenue sur Shopfront")

    def test_duplicate_email(self):
        signup("a@example.com", "A", "long-enough-pw")
        with self.assertRaises(SignupError):
            signup("A@example.com", "A2", "long-enough-pw")

    def test_short_password(self):
        with self.assertRaises(SignupError):
            signup("b@example.com", "B", "short")

    def test_smtp_failure_rolls_back_signup(self):
        # Current behavior: a mail failure aborts the whole signup.
        self.mail.fail_next = 1
        with self.assertRaises(OSError):
            signup("c@example.com", "C", "long-enough-pw")
        self.assertIsNone(db.execute("SELECT 1 FROM users WHERE email='c@example.com'").fetchone())


if __name__ == "__main__":
    unittest.main()
