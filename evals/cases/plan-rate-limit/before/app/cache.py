"""The shared Redis client. One connection pool per process."""
from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger(__name__)
_client = None


def get_redis():
    """Return the process-wide Redis client, creating it on first use."""
    global _client
    if _client is None:
        import redis  # imported lazily so tests don't need the package
        _client = redis.Redis.from_url(
            settings.redis_url,
            socket_timeout=0.25,
            socket_connect_timeout=0.25,
            decode_responses=True,
        )
    return _client


def set_client(client) -> None:
    """Swap the client (tests use tests.fakes.FakeRedis)."""
    global _client
    _client = client


class CacheUnavailable(Exception):
    """Redis couldn't be reached. Callers decide whether that's fatal."""


def call(fn, *args, **kwargs):
    """Run a Redis operation, turning connection errors into CacheUnavailable."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # redis.ConnectionError / TimeoutError
        if type(exc).__name__ in ("ConnectionError", "TimeoutError"):
            log.warning("redis unavailable: %s", exc)
            raise CacheUnavailable(str(exc)) from exc
        raise
