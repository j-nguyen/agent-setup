"""Human-readable text output."""
from __future__ import annotations

from tally.models import Entry, Report


def entries_table(entries: list[Entry]) -> str:
    if not entries:
        return "No entries."
    lines = [f"{'DATE':<10}  {'PROJECT':<12}  {'HOURS':>5}  NOTE"]
    for e in entries:
        lines.append(f"{e.day.isoformat():<10}  {e.project:<12}  {e.hours:>5.2f}  {e.note}")
    return "\n".join(lines)


def report_table(report: Report) -> str:
    if not report.rows:
        return "No entries in this period."
    lines = [f"{'PROJECT':<12}  {'HOURS':>6}  {'ENTRIES':>7}  {'SHARE':>6}"]
    for r in report.rows:
        lines.append(f"{r.project:<12}  {r.hours:>6.2f}  {r.entries:>7}  {r.share:>6.1%}")
    lines.append(f"{'TOTAL':<12}  {report.total_hours:>6.2f}")
    return "\n".join(lines)
