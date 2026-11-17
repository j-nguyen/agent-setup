"""Account subscriptions: which plans an account is on."""

ACTIVE_STATUSES = ("trialing", "active")


def subscribe(conn, account_id: int, plan_id: int, status: str = "active") -> None:
    """Subscribe an account to a plan. Subscribing twice is a no-op."""
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscriptions (account_id, plan_id, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (account_id, plan_id) DO NOTHING
                """,
                (account_id, plan_id, status),
            )


def active_subscriptions(conn, account_id: int) -> list[tuple]:
    """Active (or trialing) subscriptions for one account, newest first."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, p.code, s.status, s.started_at
            FROM subscriptions s
            JOIN plans p ON p.id = s.plan_id
            WHERE s.account_id = %s AND s.status IN %s
            ORDER BY s.started_at DESC
            """,
            (account_id, ACTIVE_STATUSES),
        )
        return cur.fetchall()

