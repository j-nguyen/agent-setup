from __future__ import annotations

import functools

from app import api_keys, sessions
from app.config import settings
from app.http import Request, error_response


def require_api_key(handler):
    """Reject requests without a valid API key; attach it as request.api_key."""
    @functools.wraps(handler)
    def wrapper(request: Request):
        key = api_keys.lookup(request.header(settings.api_key_header))
        if key is None:
            return error_response(401, "invalid_api_key", "Missing or invalid API key")
        request.api_key = key
        return handler(request)
    return wrapper


def _cookie(request: Request, name: str) -> str | None:
    for part in (request.header("cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return None


def require_session(handler):
    @functools.wraps(handler)
    def wrapper(request: Request):
        session = sessions.load(_cookie(request, settings.session_cookie))
        if session is None:
            return error_response(401, "not_logged_in", "Log in first")
        request.session = session
        return handler(request)
    return wrapper
