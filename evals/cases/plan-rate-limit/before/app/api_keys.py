"""API keys issued to partners. Loaded from the partners table at startup."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiKey:
    key_id: str
    partner: str
    plan: str  # "free" | "pro"
    digest: str


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# In production this is loaded from the partners table; the shape is the same.
_KEYS: dict[str, ApiKey] = {}


def register(key_id: str, partner: str, plan: str, raw: str) -> ApiKey:
    k = ApiKey(key_id, partner, plan, _digest(raw))
    _KEYS[k.digest] = k
    return k


def lookup(raw: str | None) -> ApiKey | None:
    if not raw:
        return None
    d = _digest(raw)
    k = _KEYS.get(d)
    if k and hmac.compare_digest(k.digest, d):
        return k
    return None


def clear() -> None:
    _KEYS.clear()
