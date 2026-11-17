from __future__ import annotations

import functools
import logging

from app.cache import CacheUnavailable
from app.http import Request, error_response

log = logging.getLogger(__name__)


def handle_errors(handler):
    """Map unexpected exceptions to the standard JSON error shape."""
    @functools.wraps(handler)
    def wrapper(request: Request):
        try:
            return handler(request)
        except CacheUnavailable:
            return error_response(503, "unavailable", "Temporarily unavailable")
        except Exception:
            log.exception("unhandled error (request_id=%s)", request.request_id)
            return error_response(500, "internal", "Internal error")
    return wrapper
