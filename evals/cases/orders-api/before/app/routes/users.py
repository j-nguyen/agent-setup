from flask import Blueprint, abort, jsonify

from app.auth import can_access_user, require_login
from app.db import query_one

bp = Blueprint("users", __name__)


@bp.get("/users/<int:user_id>")
@require_login
def get_user(user_id: int):
    if not can_access_user(user_id):
        abort(403)
    user = query_one("SELECT id, email, name FROM users WHERE id = %s", [user_id])
    if user is None:
        abort(404)
    return jsonify(user)
