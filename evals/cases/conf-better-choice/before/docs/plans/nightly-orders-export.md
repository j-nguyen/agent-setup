# Plan: Nightly orders CSV export

**Status:** Accepted
**Date:** 2026-11-04
**Scope:** A `ledger export` command that writes every order to a dated CSV for finance.

## Goal
Finance imports a full orders CSV each morning. Produce `orders-YYYY-MM-DD.csv` in the export
directory every night, without loading the whole table (~3M rows) into memory.

## Requirements
- R1: One CSV per day with every order, header `id,customer_id,total_cents,status,created_at`.
- R2: Bounded memory regardless of table size.
- R3: Finance's importer must never see a half-written file.
**Non-goals:** Incremental exports; scheduling inside the app (the existing cron runs commands).

## Current state
- `internal/store/orders.go:19` has single-order lookups only.
- `internal/config/config.go:11` reads `LEDGER_EXPORT_DIR`.
- `cmd/ledger/main.go:31` dispatches subcommands.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A | Batches of 1000 with `ORDER BY id LIMIT/OFFSET` | Simple, bounded memory | Later pages scan skipped rows |
| B | One streaming query over a server-side cursor | Fastest | Holds one transaction open for minutes |
**Chosen:** A, because it keeps transactions short and is simple to test with a fake pager.

## Decisions
- **D1:** New package `internal/export` with `Write(ctx, src, w)` and `ToFile(ctx, src, dir, day)`; `src` is a small pager interface the store implements. *Why:* testable without a database.
- **D2:** Write to a temp file in the export dir, then `os.Rename` to the final name. *Why:* R3; rename is atomic on one filesystem.
- **D3:** Read orders in batches of 1000 with `ORDER BY id LIMIT $1 OFFSET $2` via `store.PageOrders(ctx, offset, limit)`. The batch size is `ExportBatchSize` in `internal/config/config.go`. *Why:* bounded memory, short queries. *Rejected:* B.
- **D4:** Amounts as integer cents, timestamps RFC 3339 in UTC. *Why:* no float rounding; finance's importer expects UTC.
- **D5:** Triggered by `ledger export` from the existing cron. *Why:* no scheduler in the app.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Pager | `internal/store/orders.go` | changed | Page through orders by id (D3) |
| Export | `internal/export/export.go` | new | CSV writing and the temp-file rename |
| Command | `cmd/ledger/main.go` | changed | `export` subcommand; logs the row count and path |
### Boundaries
- `internal/export` must not import `cmd/...` or `net/http`.

## Implementation steps
1. Pager plus `config.ExportBatchSize`: `internal/store/orders.go`, `internal/config/config.go`. *Done when:* pages come back in id order.
2. Export package: `internal/export/export.go`. *Done when:* the Test plan passes.
3. Subcommand: `cmd/ledger/main.go`. *Done when:* `ledger export` writes today's file and logs it.

## Test plan
- Unit (fake pager): 2,500 orders produce a header plus 2,500 rows in id order across three batches.
- Unit: a pager error leaves no file in the export dir.
- Unit: cents and UTC timestamps are formatted as in D4.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Export slows as the table grows | Medium | Revisit when it passes 10 minutes |

## Conformance checklist
- [ ] C1: `internal/export` doesn't import `cmd/...` or `net/http` (D1, step 2)
- [ ] C2: Orders are read in batches with `ORDER BY id LIMIT/OFFSET` through `PageOrders` (D3, step 1)
- [ ] C3: The batch size is `config.ExportBatchSize` = 1000, not a literal in the export code (D3, step 1)
- [ ] C4: Columns match R1; amounts are integer cents and timestamps RFC 3339 UTC (D4, step 2)
- [ ] C5: The file is written to a temp file in the export dir and renamed into place; errors leave no file (D2, step 2)
- [ ] C6: `ledger export` runs the export and logs the row count and path; there's no in-app scheduler (D5, step 3)
- [ ] C7: Tests cover the multi-batch export, the error path and formatting (step 2)

## Deviation log
