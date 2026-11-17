import re

from app.errors import AppError
from app.handlers import customers, orders

ROUTES = [
    ("GET", re.compile(r"^/orders/(?P<order_id>[^/]+)$"), orders.get_order),
    ("GET", re.compile(r"^/customers/(?P<customer_id>[^/]+)/summary$"), customers.get_summary),
    ("GET", re.compile(r"^/customers/(?P<customer_id>[^/]+)/orders/recent$"), customers.get_recent_orders),
]


def dispatch(conn, method: str, path: str, query: dict | None = None) -> tuple[int, dict]:
    for route_method, pattern, handler in ROUTES:
        match = pattern.match(path)
        if match and route_method == method:
            request = {"params": match.groupdict(), "query": query or {}}
            try:
                return handler(conn, request)
            except AppError as e:
                return e.status, {"error": e.message}
    return 404, {"error": "no such route"}
