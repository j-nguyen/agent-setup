"""Read and append entries in the JSON-lines file."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from tally.models import Entry


def default_path() -> Path:
    return Path(os.environ.get("TALLY_FILE", Path.home() / ".tally" / "entries.jsonl"))


def append(entry: Entry, path: Path | None = None) -> None:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"day": entry.day.isoformat(), "project": entry.project,
                            "hours": entry.hours, "note": entry.note}) + "\n")


def load(path: Path | None = None, since: date | None = None,
         until: date | None = None) -> list[Entry]:
    path = path or default_path()
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        e = Entry(date.fromisoformat(d["day"]), d["project"], float(d["hours"]), d.get("note", ""))
        if since and e.day < since:
            continue
        if until and e.day > until:
            continue
        out.append(e)
    return out
