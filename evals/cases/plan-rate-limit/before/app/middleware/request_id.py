from __future__ import annotations

import functools
import uuid

from app.http import Request


def with_request_id(handler):
    """Accept or create an X-Request-Id and echo it on the response."""
    @functools.wraps(handler)
    def wrapper(request: Request):
        request.request_id = request.header("x-request-id") or uuid.uuid4().hex
        response = handler(request)
        response.headers["X-Request-Id"] = request.request_id
        return response
    return wrapper
