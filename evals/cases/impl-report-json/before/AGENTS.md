# Notes for contributors

- `tally/cli.py` is only argument parsing and wiring. Logic lives in
  `tally/store.py` (reading/writing entries), `tally/reports.py` (aggregation)
  and `tally/render.py` (human-readable text output).
- `tally/serialize.py` is the one place that turns our dataclasses into JSON.
  Use it rather than calling `json.dumps` on dataclasses yourself.
- CLI tests call `tally.cli.main(argv)` and capture stdout; see
  `tests/test_cli.py`.
- Keep the standard library only; no third-party dependencies.
