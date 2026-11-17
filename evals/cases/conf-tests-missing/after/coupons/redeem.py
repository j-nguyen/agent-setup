import sqlite3

from coupons.pricing import Coupon, get_coupon


class CouponError(Exception):
    """Base class for redemption failures shown to the shopper."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class CouponNotFound(CouponError):
    pass


class CouponExpired(CouponError):
    pass


class CouponExhausted(CouponError):
    pass


class CouponAlreadyRedeemed(CouponError):
    pass


def redeem(conn: sqlite3.Connection, code: str, user_id: str, now: str) -> Coupon:
    """Redeem `code` for `user_id` at time `now` (ISO 8601, UTC) and return the updated coupon."""
    code = code.upper()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "UPDATE coupons SET redeemed_count = redeemed_count + 1 "
            "WHERE code = ? AND redeemed_count < max_redemptions AND expires_at > ?",
            (code, now),
        )
        if cur.rowcount == 0:
            raise _why_not(conn, code, now)
        try:
            conn.execute(
                "INSERT INTO redemptions (code, user_id, redeemed_at) VALUES (?, ?, ?)",
                (code, user_id, now),
            )
        except sqlite3.IntegrityError:
            raise CouponAlreadyRedeemed(code) from None
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return get_coupon(conn, code)


def _why_not(conn: sqlite3.Connection, code: str, now: str) -> CouponError:
    coupon = get_coupon(conn, code)
    if coupon is None:
        return CouponNotFound(code)
    if coupon.expires_at <= now:
        return CouponExpired(code)
    return CouponExhausted(code)
