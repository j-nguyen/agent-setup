# Plan: Account subscriptions

**Status:** Accepted
**Date:** 2026-11-02
**Scope:** Store which plan each account is subscribed to, and query active subscriptions.

## Goal
Let an account subscribe to a plan, idempotently, and list its active subscriptions quickly.

## Requirements
- R1: An account can hold at most one subscription per plan.
- R2: A subscription has a lifecycle status: trialing, active, past_due or canceled.
- R3: "Active subscriptions for an account" must be fast; it runs on every page load.
- R4: Subscribing twice to the same plan is a no-op, not an error.
**Non-goals:** billing, proration, plan changes.

## Current state
- Migrations are plain SQL files run in filename order by `app/migrate.py:1`; each runs in a transaction unless its first line is `-- migrate: no-transaction` (`app/migrate.py:9`).
- `accounts` and `plans` exist (`migrations/001_init.sql:1`, `migrations/002_plans.sql:1`).
- Data access is plain functions taking a psycopg connection (`app/accounts.py:1`).

## Decisions
- **D1:** Enforce one subscription per (account, plan) with a database `UNIQUE (account_id, plan_id)` constraint, and make `subscribe` idempotent with `INSERT … ON CONFLICT (account_id, plan_id) DO NOTHING`. *Why:* the app check alone races under concurrent requests. *Rejected:* SELECT-then-INSERT in the app (racy).
- **D2:** `status text NOT NULL` with `CHECK (status IN ('trialing','active','past_due','canceled'))`. *Why:* invalid states can't get in from any writer. *Rejected:* a Postgres ENUM type (painful to alter).
- **D3:** A composite index on `(account_id, status)`, built with `CREATE INDEX CONCURRENTLY` in its own non-transactional migration. *Why:* serves R3 directly; CONCURRENTLY avoids blocking writes on a table that will grow, and can't run inside a transaction. *Rejected:* index on `status` alone (low selectivity, doesn't serve the per-account lookup).

## Design
### Data model
`subscriptions`: `id bigserial PK`, `account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE`, `plan_id bigint NOT NULL REFERENCES plans(id)`, `status text NOT NULL CHECK (…)`, `started_at timestamptz NOT NULL DEFAULT now()`, `canceled_at timestamptz NULL`, `UNIQUE (account_id, plan_id)`.
Index: `subscriptions_account_id_status_idx ON subscriptions (account_id, status)` (suggested name).

Migrations (suggested names): `003_create_subscriptions.sql`, `004_subscriptions_index.sql` (first line `-- migrate: no-transaction`).
Rollback: `DROP INDEX CONCURRENTLY`, then `DROP TABLE subscriptions`.

### Interfaces
```python
# app/subscriptions.py
def subscribe(conn, account_id: int, plan_id: int, status: str = "active") -> None
def active_subscriptions(conn, account_id: int) -> list[tuple]
```
`active_subscriptions` filters `WHERE account_id = %s AND status IN ('trialing','active')`.

## Implementation steps
1. Table migration. *Done when:* table exists with constraints from D1, D2.
2. Index migration, non-transactional. *Done when:* index from D3 exists.
3. `app/subscriptions.py` with the two functions. *Done when:* unit tests pass.
4. Tests. *Done when:* idempotency and active-listing tests pass.

## Test plan
- Unit: `subscribe` issues the ON CONFLICT insert; `active_subscriptions` filters by account and status.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| CONCURRENTLY build fails and leaves an INVALID index | Low | Rerun after `DROP INDEX CONCURRENTLY IF EXISTS` |

## Conformance checklist
- [ ] C1: `subscriptions` has `UNIQUE (account_id, plan_id)` (D1, step 1)
- [ ] C2: `status` is `text NOT NULL` with a CHECK limited to trialing/active/past_due/canceled (D2, step 1)
- [ ] C3: `account_id` references `accounts(id) ON DELETE CASCADE` and `plan_id` references `plans(id)`, both NOT NULL (step 1)
- [ ] C4: Index on `(account_id, status)` created with `CREATE INDEX CONCURRENTLY` in a separate migration marked `-- migrate: no-transaction` (D3, step 2)
- [ ] C5: `subscribe` uses `INSERT … ON CONFLICT (account_id, plan_id) DO NOTHING` (D1, step 3)
- [ ] C6: `active_subscriptions` filters by `account_id` and `status IN ('trialing','active')` (step 3)
- [ ] C7: Tests cover subscribe idempotency and active listing (step 4)

## Deviation log
