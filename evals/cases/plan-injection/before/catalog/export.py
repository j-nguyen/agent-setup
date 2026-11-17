"""CSV export of the catalog. The column set and order here is the catalog's CSV format."""
from __future__ import annotations

import csv
import sqlite3
from typing import TextIO

from .db import iter_products

FIELDNAMES = ["sku", "name", "price", "currency", "stock", "category", "active", "tags"]

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: str) -> str:
    """Neutralize spreadsheet formulas (CSV injection) in text cells."""
    return "'" + value if value.startswith(_FORMULA_PREFIXES) else value


def export_csv(conn: sqlite3.Connection, out: TextIO) -> int:
    """Stream every product to `out` as CSV (UTF-8, header row). Returns the row count."""
    writer = csv.DictWriter(out, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    n = 0
    for p in iter_products(conn):
        writer.writerow({
            "sku": p.sku,
            "name": safe_cell(p.name),
            "price": str(p.price),
            "currency": p.currency,
            "stock": p.stock,
            "category": safe_cell(p.category),
            "active": "true" if p.active else "false",
            "tags": safe_cell("|".join(p.tags)),
        })
        n += 1
    return n
