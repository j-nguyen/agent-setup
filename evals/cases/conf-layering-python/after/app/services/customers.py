from app.errors import NotFound
from app.storage import customers_repo, orders_repo


def require_customer(conn, customer_id: int) -> None:
    if customers_repo.get(conn, customer_id) is None:
        raise NotFound(f"customer {customer_id} not found")


def _to_summary_dict(customer_id: int, row) -> dict:
    return {
        "customer_id": customer_id,
        "order_count": row["order_count"],
        "total_cents": row["total_cents"],
        "last_order_at": row["last_order_at"],
    }


def customer_summary(conn, customer_id: int) -> dict:
    require_customer(conn, customer_id)
    row = orders_repo.summarize_for_customer(conn, customer_id)
    return _to_summary_dict(customer_id, row)
