from coupons.db import connect, migrate


def memory_db():
    """Fresh in-memory database with the schema applied."""
    conn = connect(":memory:")
    migrate(conn)
    return conn


def add_coupon(conn, code="SAVE10", percent_off=10, expires_at="2099-01-01T00:00:00Z", max_redemptions=100):
    conn.execute(
        "INSERT INTO coupons (code, percent_off, expires_at, max_redemptions) VALUES (?, ?, ?, ?)",
        (code, percent_off, expires_at, max_redemptions),
    )
