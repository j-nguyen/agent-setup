PROJ-101: Machine-readable output for `tally report`

**Reported by:** Product (Dana) · **Priority:** Medium · **Labels:** cli, feature

Our ops team runs `tally report` from cron and scrapes the text table with awk, which breaks every time a project name has a space. They need a machine-readable version they can pipe into jq.

Acceptance criteria: (1) `tally report --json` prints the report as JSON on stdout. (2) The JSON has the same shape as the `report` object that `tally export` already writes. (3) Without `--json`, output is exactly what it is today. (4) An empty period still prints valid JSON. (5) Covered by a test.

Comment from Dana (Product): Could we make this pluggable so we can add CSV, YAML and maybe XML outputs later without touching the command? Some kind of formatter framework would future-proof it.

Comment from Lee (Tech lead): Let's not build a framework for formats nobody has asked for yet. JSON only for this ticket; CSV is tracked separately in PROJ-140. Reuse the serializer the export command already uses.
