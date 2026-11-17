"""Registry of job handlers: kind -> function(payload)."""
from __future__ import annotations

from typing import Callable

HANDLERS: dict[str, Callable[[dict], None]] = {}


def handler(kind: str):
    def register(fn: Callable[[dict], None]):
        HANDLERS[kind] = fn
        return fn
    return register
