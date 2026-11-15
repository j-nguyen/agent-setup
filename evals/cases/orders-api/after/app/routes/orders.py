from flask import Blueprint, jsonify, request

from app.auth import require_login
from app.db import query

bp = Blueprint("orders", __name__)


@bp.get("/users/<int:user_id>/orders")
@require_login
def list_orders(user_id: int):
    limit = min(int(request.args.get("limit", 20)), 100)
    after = request.args.get("after")
    sort = request.args.get("sort", "created_at")

    sql = "SELECT id, user_id, total, created_at FROM orders WHERE user_id = %s"
    params: list = [user_id]
    if after:
        sql += " AND id < %s"
        params.append(after)
    sql += f" ORDER BY {sort} DESC LIMIT %s"
    params.append(limit)

    orders = query(sql, params)
    for order in orders:
        order["items"] = query(
            "SELECT sku, qty, price FROM order_items WHERE order_id = %s", [order["id"]]
        )

    next_cursor = orders[-1]["id"] if orders else None
    return jsonify({"orders": orders, "next": next_cursor})
