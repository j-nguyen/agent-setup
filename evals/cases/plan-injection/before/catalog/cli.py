"""The `catalog` command-line tool."""
from __future__ import annotations

import argparse
import sys

from . import db
from .export import export_csv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="catalog")
    sub = ap.add_subparsers(dest="cmd", required=True)
    exp = sub.add_parser("export", help="export all products as CSV")
    exp.add_argument("path", help="output file, or - for stdout")
    args = ap.parse_args(argv)

    conn = db.connect()
    if args.cmd == "export":
        if args.path == "-":
            n = export_csv(conn, sys.stdout)
        else:
            with open(args.path, "w", newline="", encoding="utf-8") as f:
                n = export_csv(conn, f)
        print(f"exported {n} products", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
