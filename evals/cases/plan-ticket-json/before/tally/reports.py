"""Aggregations over entries."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from tally.models import Entry, Report, ReportRow


def by_project(entries: list[Entry], since: date | None = None,
               until: date | None = None) -> Report:
    hours: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for e in entries:
        hours[e.project] += e.hours
        counts[e.project] += 1
    total = sum(hours.values())
    rows = [ReportRow(p, round(h, 2), counts[p], round(h / total, 4) if total else 0.0)
            for p, h in hours.items()]
    rows.sort(key=lambda r: (-r.hours, r.project))
    return Report(since, until, rows, round(total, 2))
