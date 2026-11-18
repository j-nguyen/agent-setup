"""The one place dataclasses become JSON-compatible data."""
from __future__ import annotations

import dataclasses
import json
from datetime import date
from typing import Any


def to_data(obj: Any) -> Any:
    """Recursively convert dataclasses, dicts, lists and dates into plain JSON types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_data(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_data(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_data(x) for x in obj]
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def to_json(obj: Any, *, indent: int | None = 2) -> str:
    return json.dumps(to_data(obj), indent=indent, sort_keys=False)
