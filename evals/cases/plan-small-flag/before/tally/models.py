from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Entry:
    day: date
    project: str
    hours: float
    note: str = ""


@dataclass(frozen=True)
class ReportRow:
    project: str
    hours: float
    entries: int
    share: float  # fraction of total hours, 0..1


@dataclass(frozen=True)
class Report:
    since: date | None
    until: date | None
    rows: list[ReportRow]
    total_hours: float
