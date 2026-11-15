from functools import wraps

from flask import abort, g


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, "user", None) is None:
            abort(401)
        return fn(*args, **kwargs)

    return wrapper
