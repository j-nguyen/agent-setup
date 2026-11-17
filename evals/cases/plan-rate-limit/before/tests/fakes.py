"""In-memory stand-ins for external services."""
from __future__ import annotations

import time


class FakeRedis:
    """Implements the subset of redis-py the app uses (decode_responses=True)."""

    def __init__(self, now=time.time):
        self._data: dict[str, tuple[str, float | None]] = {}
        self._now = now
        self.down = False

    def _check(self):
        if self.down:
            ConnectionError = type("ConnectionError", (Exception,), {})
            raise ConnectionError("fake redis is down")

    def _alive(self, key):
        v = self._data.get(key)
        if v and v[1] is not None and v[1] <= self._now():
            del self._data[key]
            return None
        return v

    def get(self, key):
        self._check()
        v = self._alive(key)
        return v[0] if v else None

    def set(self, key, value, ex=None, nx=False):
        self._check()
        if nx and self._alive(key):
            return None
        self._data[key] = (str(value), self._now() + ex if ex else None)
        return True

    def setex(self, key, seconds, value):
        return self.set(key, value, ex=seconds)

    def delete(self, *keys):
        self._check()
        return sum(1 for k in keys if self._data.pop(k, None) is not None)

    def incr(self, key, amount=1):
        self._check()
        v = self._alive(key)
        n = int(v[0]) + amount if v else amount
        self._data[key] = (str(n), v[1] if v else None)
        return n

    def expire(self, key, seconds):
        self._check()
        v = self._alive(key)
        if not v:
            return False
        self._data[key] = (v[0], self._now() + seconds)
        return True

    def ttl(self, key):
        self._check()
        v = self._alive(key)
        if not v:
            return -2
        return -1 if v[1] is None else int(v[1] - self._now())
