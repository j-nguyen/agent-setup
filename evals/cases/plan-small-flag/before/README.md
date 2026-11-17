# tally

A small command-line time tracker. Entries live in a JSON-lines file
(`~/.tally/entries.jsonl`, or `$TALLY_FILE`).

```sh
tally add acme 1.5 "API review"          # log 1.5 hours on project acme
tally list --since 2026-11-01            # list entries
tally report --since 2026-11-01          # hours per project, as a table
tally export --since 2026-11-01 -o out.json   # write entries + report to a file
```

## Development

```sh
python3 -m unittest discover -s tests -t .
```
