"""Command-line entry point: argument parsing and wiring only."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from tally import render, reports, serialize, store
from tally.models import Entry


def _date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date (YYYY-MM-DD): {s}")


def _add_period(p: argparse.ArgumentParser) -> None:
    p.add_argument("--since", type=_date, help="first day to include (YYYY-MM-DD)")
    p.add_argument("--until", type=_date, help="last day to include (YYYY-MM-DD)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tally", description="A small time tracker.")
    parser.add_argument("--file", type=Path, help="entries file (default: $TALLY_FILE or ~/.tally/entries.jsonl)")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="log time")
    add.add_argument("project")
    add.add_argument("hours", type=float)
    add.add_argument("note", nargs="?", default="")
    add.add_argument("--day", type=_date, default=None, help="default: today")

    lst = sub.add_parser("list", help="list entries")
    _add_period(lst)

    rep = sub.add_parser("report", help="hours per project")
    _add_period(rep)

    exp = sub.add_parser("export", help="write entries and the report as JSON")
    _add_period(exp)
    exp.add_argument("-o", "--output", type=Path, required=True)
    return parser


def cmd_add(args) -> int:
    if args.hours <= 0:
        print("hours must be positive", file=sys.stderr)
        return 2
    store.append(Entry(args.day or date.today(), args.project, args.hours, args.note), args.file)
    return 0


def cmd_list(args) -> int:
    print(render.entries_table(store.load(args.file, args.since, args.until)))
    return 0


def cmd_report(args) -> int:
    entries = store.load(args.file, args.since, args.until)
    print(render.report_table(reports.by_project(entries, args.since, args.until)))
    return 0


def cmd_export(args) -> int:
    entries = store.load(args.file, args.since, args.until)
    report = reports.by_project(entries, args.since, args.until)
    args.output.write_text(serialize.to_json({"entries": entries, "report": report}) + "\n")
    print(f"Wrote {len(entries)} entries to {args.output}")
    return 0


COMMANDS = {"add": cmd_add, "list": cmd_list, "report": cmd_report, "export": cmd_export}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
