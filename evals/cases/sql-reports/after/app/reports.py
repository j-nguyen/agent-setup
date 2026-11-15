"""Admin reports and account tools."""
from __future__ import annotations

from datetime import date

from .db import query, transaction

PAGE_SIZE = 50


def daily_revenue(day: date) -> dict:
    """Revenue and order count for one UTC day (the finance dashboard calls this for the last 30 days)."""
    rows = query(
        """
        SELECT count(*) AS orders, COALESCE(sum(total_cents), 0) AS revenue_cents
        FROM orders
        WHERE date(created_at AT TIME ZONE 'UTC') = %s
          AND status = 'paid'
        """,
        (day,),
    )
    return rows[0]


def search_customers(term: str, page: int = 1) -> list[dict]:
    """Support search box: any part of the email or name, newest customers first."""
    return query(
        """
        SELECT id, email, name, country, created_at
        FROM customers
        WHERE email ILIKE '%%' || %s || '%%' OR name ILIKE '%%' || %s || '%%'
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        (term, term, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    )


def orders_by_id(order_ids: list[int]) -> list[dict]:
    return query("SELECT * FROM orders WHERE id = ANY(%s)", (order_ids,))


def customers_never_refunded(country: str) -> list[dict]:
    """Loyalty campaign: customers in `country` who have never had a refund."""
    return query(
        """
        WITH local AS (
          SELECT id, email, name FROM customers WHERE country = %s
        )
        SELECT l.id, l.email, l.name
        FROM local l
        WHERE l.id NOT IN (SELECT r.customer_id FROM refunds r)
        ORDER BY l.id
        """,
        (country,),
    )


def apply_credit(customer_id: int, amount_cents: int) -> int:
    """Add store credit (support goodwill gestures; several agents may credit the same customer)."""
    with transaction() as conn:
        row = conn.execute("SELECT credit_cents FROM customers WHERE id = %s", (customer_id,)).fetchone()
        if row is None:
            raise LookupError(customer_id)
        new_balance = row["credit_cents"] + amount_cents
        conn.execute("UPDATE customers SET credit_cents = %s WHERE id = %s", (new_balance, customer_id))
        return new_balance
