from app.errors import NotFound
from app.storage import orders_repo


def get_order(conn, order_id: int) -> dict:
    row = orders_repo.get(conn, order_id)
    if row is None:
        raise NotFound(f"order {order_id} not found")
    return dict(row)
