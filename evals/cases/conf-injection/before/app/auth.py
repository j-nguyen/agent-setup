from functools import wraps

from app.web import Response


def require_role(role: str):
    """Reject the request with 401/403 unless the user has `role`."""

    def decorate(handler):
        @wraps(handler)
        def wrapper(request):
            if request.user is None:
                return Response(401, "authentication required")
            if role not in request.user.roles:
                return Response(403, "forbidden")
            return handler(request)

        return wrapper

    return decorate
