"""All settings, read once from the environment. Nothing else reads os.environ."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Config:
    env: str
    redis_url: str
    session_ttl_seconds: int
    session_cookie: str
    api_key_header: str
    trusted_proxy_count: int


def load() -> Config:
    return Config(
        env=os.environ.get("APP_ENV", "development"),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        session_ttl_seconds=_int("SESSION_TTL_SECONDS", 8 * 3600),
        session_cookie=os.environ.get("SESSION_COOKIE", "catalog_session"),
        api_key_header=os.environ.get("API_KEY_HEADER", "X-Api-Key"),
        # The load balancer appends one X-Forwarded-For hop.
        trusted_proxy_count=_int("TRUSTED_PROXY_COUNT", 1),
    )


settings = load()
