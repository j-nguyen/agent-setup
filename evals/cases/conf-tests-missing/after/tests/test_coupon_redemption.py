import unittest

from coupons.pricing import get_coupon
from coupons.redeem import CouponAlreadyRedeemed, CouponExhausted, CouponNotFound, redeem
from tests.helpers import add_coupon, memory_db

NOW = "2026-11-10T12:00:00Z"


class RedeemTest(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()
        add_coupon(self.conn, code="SAVE10", max_redemptions=2)

    def count(self):
        return get_coupon(self.conn, "SAVE10").redeemed_count

    def test_redeem_increments_and_records(self):
        coupon = redeem(self.conn, "save10", "u1", NOW)
        self.assertEqual(coupon.redeemed_count, 1)
        rows = self.conn.execute("SELECT user_id FROM redemptions WHERE code = 'SAVE10'").fetchall()
        self.assertEqual([r["user_id"] for r in rows], ["u1"])

    def test_same_user_twice(self):
        redeem(self.conn, "SAVE10", "u1", NOW)
        with self.assertRaises(CouponAlreadyRedeemed):
            redeem(self.conn, "SAVE10", "u1", NOW)
        self.assertEqual(self.count(), 1)

    def test_exhausted(self):
        redeem(self.conn, "SAVE10", "u1", NOW)
        redeem(self.conn, "SAVE10", "u2", NOW)
        with self.assertRaises(CouponExhausted):
            redeem(self.conn, "SAVE10", "u3", NOW)
        self.assertEqual(self.count(), 2)

    def test_unknown_code(self):
        with self.assertRaises(CouponNotFound):
            redeem(self.conn, "NOPE", "u1", NOW)


if __name__ == "__main__":
    unittest.main()
