from app.errors import ValidationError
from app.services import orders


def get_order(conn, request: dict) -> tuple[int, dict]:
    try:
        order_id = int(request["params"]["order_id"])
    except (KeyError, ValueError):
        raise ValidationError("order_id must be an integer")
    return 200, orders.get_order(conn, order_id)
