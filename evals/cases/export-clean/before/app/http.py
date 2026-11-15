"""Tiny request/response types shared by the admin handlers (the WSGI glue lives elsewhere)."""
from dataclasses import dataclass, field


@dataclass
class Response:
    status: int
    headers: dict = field(default_factory=dict)
    body: bytes = b""


class BadRequest(Exception):
    """Raised by input parsing; handlers turn it into a 400."""
