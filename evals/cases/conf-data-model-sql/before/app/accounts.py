def get_account(conn, account_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT id, email, created_at FROM accounts WHERE id = %s", (account_id,))
        return cur.fetchone()
