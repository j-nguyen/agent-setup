# SQL and data access

Examples are PostgreSQL. Adapt to the repo's database and ORM.

**Safety**
- Parameterize every value. Never build SQL by concatenating or formatting
  input. Identifiers that must vary (sort column, table) come from a fixed
  allowlist in code.
- Scope every query that reads or writes tenant- or user-owned rows by the
  owner (`WHERE tenant_id = $1`), in the query itself, not afterwards in code.
- Use the least-privileged connection the repo provides. No credentials in code
  or migrations.

**Queries**
- Select the columns you need, not `SELECT *`, in application queries.
- No N+1: load related rows with a join, `IN (…)` / `= ANY($1)`, or the ORM's
  eager loading (`select_related`, `prefetch_related`, `include`, `joinedload`).
- Every list endpoint is bounded: `LIMIT`, plus keyset pagination
  (`WHERE (created_at, id) < ($1, $2) ORDER BY created_at DESC, id DESC`) for
  large tables. `OFFSET` only for small, bounded sets.
- `ORDER BY` a unique key (or add `id` as a tiebreaker) so pagination is stable.
- Filters and joins on large tables have a supporting index. A predicate that
  wraps the column (`lower(email)`, `date(created_at)`) needs a matching
  expression index, or rewrite it as a range.
- Count with `EXISTS` when you only need to know if a row exists.
- Aggregate in the database, not by loading rows into application memory.

**Transactions and concurrency**
- Wrap multi-statement writes that must succeed together in one transaction.
  Keep transactions short. No network calls (HTTP, email, queues) inside them;
  do side effects after commit (or through an outbox if the repo has one).
- Prevent lost updates on read-modify-write: a single `UPDATE … SET x = x + 1`,
  `SELECT … FOR UPDATE`, or an optimistic version check.
- Enforce invariants with constraints (`NOT NULL`, `UNIQUE`, `CHECK`, foreign
  keys), not only in code. Use `INSERT … ON CONFLICT` for idempotent upserts.

**Migrations**
- Follow the repo's migration tool and naming. One logical change per
  migration, with a working down/rollback if the tool supports it.
- On large or busy tables: `CREATE INDEX CONCURRENTLY` (outside a transaction);
  add a column as nullable or with a constant default, backfill in batches,
  then add `NOT NULL`; add foreign keys and checks `NOT VALID`, then `VALIDATE`.
- Never rename or drop a column that deployed code still reads. Expand first,
  switch the code, contract in a later migration.
- Don't edit a migration that has already been applied anywhere; add a new one.

**Types**: `timestamptz` for times, `numeric` (or integer minor units) for
money, never `float`. `text` with a `CHECK` over arbitrary `varchar(n)` limits
unless the repo does otherwise.

**Tests**: test queries against a real database of the same engine when the
repo's test setup has one, including the empty result and the tenant/owner filter.
