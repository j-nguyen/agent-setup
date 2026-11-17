from app.errors import ValidationError
from app.services import customers
from app.storage import orders_repo

DEFAULT_LIMIT = 5
MAX_LIMIT = 50


def _customer_id(request: dict) -> int:
    try:
        return int(request["params"]["customer_id"])
    except (KeyError, ValueError):
        raise ValidationError("customer_id must be an integer")


def _limit(request: dict) -> int:
    raw = request["query"].get("limit")
    if raw is None:
        return DEFAULT_LIMIT
    try:
        limit = int(raw)
    except ValueError:
        raise ValidationError("limit must be an integer")
    return max(1, min(limit, MAX_LIMIT))


def get_summary(conn, request: dict) -> tuple[int, dict]:
    return 200, customers.customer_summary(conn, _customer_id(request))


def get_recent_orders(conn, request: dict) -> tuple[int, dict]:
    customer_id = _customer_id(request)
    limit = _limit(request)
    customers.require_customer(conn, customer_id)
    rows = orders_repo.list_recent_for_customer(conn, customer_id, limit)
    return 200, {"items": [dict(r) for r in rows]}
