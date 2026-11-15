"""Admin CSV export of orders."""
from __future__ import annotations

import csv
import hashlib
import io
import logging
from pathlib import Path

import yaml

from .auth import User
from .http import BadRequest, Response

log = logging.getLogger(__name__)

PRESETS_FILE = Path(__file__).parent.parent / "config" / "export_presets.yaml"

# Export column name -> SQL expression. Only these fixed strings are ever put into
# the SELECT list, so user input never reaches the SQL text.
EXPORTABLE = {
    "id": "o.id",
    "customer_email": "c.email",
    "customer_name": "c.name",
    "total_cents": "o.total_cents",
    "status": "o.status",
    "created_at": "o.created_at",
}
DEFAULT_COLUMNS = ["id", "customer_email", "total_cents", "created_at"]

# A text cell starting with one of these is run as a formula by spreadsheet apps.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def load_presets(path: Path = PRESETS_FILE) -> dict[str, list[str]]:
    data = yaml.safe_load(path.read_text()) or {}
    return {str(name): [str(c) for c in cols] for name, cols in data.items()}


def parse_columns(columns: str | None, preset: str | None, presets: dict[str, list[str]]) -> list[str]:
    if columns:
        cols = [c.strip() for c in columns.split(",") if c.strip()]
    elif preset:
        if preset not in presets:
            raise BadRequest(f"unknown preset {preset!r}")
        cols = list(presets[preset])
    else:
        cols = list(DEFAULT_COLUMNS)
    unknown = [c for c in cols if c not in EXPORTABLE]
    if not cols or unknown:
        raise BadRequest(f"unknown column(s): {', '.join(unknown) or '(none given)'}")
    return list(dict.fromkeys(cols))  # drop repeats, keep order


def safe_cell(value) -> object:
    """Neutralize spreadsheet formulas in text cells. Numbers are left as numbers."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def export_orders_csv(db, user: User, columns: str | None = None, preset: str | None = None,
                      if_none_match: str | None = None, presets: dict[str, list[str]] | None = None) -> Response:
    if not user.is_admin:
        return Response(403)
    try:
        cols = parse_columns(columns, preset, load_presets() if presets is None else presets)
    except BadRequest as e:
        return Response(400, {"Content-Type": "text/plain; charset=utf-8"}, str(e).encode())

    select_list = ", ".join(f"{EXPORTABLE[c]} AS {c}" for c in cols)
    rows = db.execute(
        f"SELECT {select_list} FROM orders o JOIN customers c ON c.id = o.customer_id ORDER BY o.id"
    ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    writer.writerows([safe_cell(v) for v in row] for row in rows)
    body = buf.getvalue().encode("utf-8")

    # Content fingerprint for caching, not a security use of SHA-1.
    etag = '"' + hashlib.sha1(body).hexdigest() + '"'
    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="orders.csv"',
        "ETag": etag,
        "Cache-Control": "private, no-cache",
    }
    log.info("orders export by admin %s: %d rows, columns=%s", user.id, len(rows), ",".join(cols))
    if if_none_match and etag in (t.strip() for t in if_none_match.split(",")):
        return Response(304, headers)
    return Response(200, headers, body)
