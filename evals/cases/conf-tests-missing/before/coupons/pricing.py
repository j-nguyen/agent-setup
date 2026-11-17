import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Coupon:
    code: str
    percent_off: int
    expires_at: str
    max_redemptions: int
    redeemed_count: int


def get_coupon(conn: sqlite3.Connection, code: str) -> Coupon | None:
    row = conn.execute(
        "SELECT code, percent_off, expires_at, max_redemptions, redeemed_count FROM coupons WHERE code = ?",
        (code.upper(),),
    ).fetchone()
    return Coupon(**dict(row)) if row else None


def apply_discount(total_cents: int, coupon: Coupon) -> int:
    """Discounted total, rounding the discount down so we never over-discount."""
    return total_cents - (total_cents * coupon.percent_off) // 100
