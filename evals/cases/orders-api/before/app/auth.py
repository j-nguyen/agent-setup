from functools import wraps

from flask import abort, g


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, "user", None) is None:
            abort(401)
        return fn(*args, **kwargs)

    return wrapper


def can_access_user(user_id: int) -> bool:
    """True if the current user may read data belonging to `user_id`."""
    return g.user["id"] == user_id or g.user["is_admin"]
