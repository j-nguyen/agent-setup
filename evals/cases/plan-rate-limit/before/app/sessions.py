"""Dashboard sessions, stored in Redis with a TTL."""
from __future__ import annotations

import json
import secrets

from app import cache
from app.config import settings

PREFIX = "session:"


def create(user: dict) -> str:
    sid = secrets.token_urlsafe(32)
    cache.call(cache.get_redis().setex, PREFIX + sid, settings.session_ttl_seconds, json.dumps(user))
    return sid


def load(sid: str | None) -> dict | None:
    if not sid:
        return None
    raw = cache.call(cache.get_redis().get, PREFIX + sid)
    return json.loads(raw) if raw else None


def destroy(sid: str) -> None:
    cache.call(cache.get_redis().delete, PREFIX + sid)
