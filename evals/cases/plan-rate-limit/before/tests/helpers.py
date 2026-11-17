from __future__ import annotations

from app import api_keys, cache, create_app
from app.http import Request
from tests.fakes import FakeRedis

FREE_KEY = "free-key-123"
PRO_KEY = "pro-key-456"


def setup_app():
    """A fresh app with a fake Redis and two API keys."""
    redis = FakeRedis()
    cache.set_client(redis)
    api_keys.clear()
    api_keys.register("k_free", "acme", "free", FREE_KEY)
    api_keys.register("k_pro", "globex", "pro", PRO_KEY)
    return create_app(), redis


def get(app, path, key=None, **headers):
    h = {k.lower().replace("_", "-"): v for k, v in headers.items()}
    if key:
        h["x-api-key"] = key
    path, _, qs = path.partition("?")
    query = dict(p.split("=", 1) for p in qs.split("&") if p)
    return app.dispatch(Request("GET", path, h, query, remote_addr="10.0.0.5"))
