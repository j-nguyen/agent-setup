# Plan: JSON output for `tally report`

**Status:** Accepted
**Date:** 2026-11-17
**Ticket:** PROJ-101
**Scope:** add `--json` to the existing `report` command

## Goal
Let scripts read the report by piping `tally report --json` into jq.

## Requirements
- R1: `tally report --json` prints the report as JSON on stdout (ticket AC1).
- R2: same shape as the `report` object `tally export` writes (ticket AC2).
- R3: without `--json`, output is unchanged (ticket AC3).
- R4: an empty period prints valid JSON (ticket AC4).
- R5: covered by a test (ticket AC5).
**Non-goals:** other formats (CSV is PROJ-140); changing the text table.

## Current state
- `tally/cli.py:39` builds the `report` subparser; `tally/cli.py:61` `cmd_report` prints `render.report_table(...)`.
- `tally/cli.py:67` `cmd_export` already writes `serialize.to_json(...)` with the `Report` from `reports.by_project`.
- `tally/serialize.py:23` `to_json` is the one JSON path (AGENTS.md).

## Decisions
- **D1:** Add a `--json` flag to the existing `report` subparser and branch in `cmd_report`. *Why:* smallest change, matches the CLI's wiring-only role. *Rejected:* a generic `--format` option or formatter classes: no second format is asked for.
- **D2:** Serialize with `serialize.to_json(report)`, the same `Report` object export uses. *Why:* one schema, one JSON path. *Rejected:* building dicts by hand.
- **D3:** With `--json`, print only the JSON to stdout, also for an empty period. *Why:* output must stay valid for jq.

## Design
### Patterns and readability
- Keep `cmd_report` a plain if/else around the two `print` calls.
- Name the flag `--json` (`args.json`), like the existing `args.since` style.

## Implementation steps
1. Add `--json` to the `report` subparser in `build_parser` and branch in `cmd_report`: `tally/cli.py`. *Done when:* `tally report --json` prints `serialize.to_json(report)` and the default path is unchanged.
2. Add tests: `tests/test_cli.py`. *Done when:* tests cover `report --json` (parsed with `json.loads`, checks `rows` and `total_hours`), an empty period with `--json`, and the existing text test still passes.

## Test plan
- Unit (CLI via `main(argv)`): `--json` happy path, empty period, text default unchanged.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Something else prints to stdout with `--json` | Low | test parses the whole stdout with `json.loads` |

## Open questions
- none

## Conformance checklist
- [ ] C1: `report` has a `--json` flag; no new command or module (D1, step 1)
- [ ] C2: JSON comes from `serialize.to_json` on the `Report` from `reports.by_project` (D2, step 1)
- [ ] C3: with `--json`, stdout is only JSON, including an empty period (D3, step 1)
- [ ] C4: text output without `--json` is unchanged (R3, step 1)
- [ ] C5: tests in `tests/test_cli.py` cover `--json`, the empty period and the text default (R5, step 2)

## Deviation log

## Noticed along the way
- `tally/render.py` repeats the hard-coded column widths in both tables; could share constants (out of scope).
