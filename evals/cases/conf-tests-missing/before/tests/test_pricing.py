import unittest

from coupons.pricing import apply_discount, get_coupon
from tests.helpers import add_coupon, memory_db


class PricingTest(unittest.TestCase):
    def test_lookup_is_case_insensitive(self):
        conn = memory_db()
        add_coupon(conn)
        self.assertEqual(get_coupon(conn, "save10").percent_off, 10)

    def test_discount_rounds_down(self):
        conn = memory_db()
        add_coupon(conn, percent_off=15)
        self.assertEqual(apply_discount(999, get_coupon(conn, "SAVE10")), 850)


if __name__ == "__main__":
    unittest.main()
