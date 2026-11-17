# Conventions

- Database access goes through `core/db.py`. Multi-step writes use
  `with db.atomic():`. Side effects that must only happen if the data is
  committed (email, jobs that read the new rows, webhooks) go in
  `db.on_commit(fn)`; never call them inside the `atomic()` block.
- Background work uses our own queue: `jobs.queue.enqueue(...)` writes a row to
  the `jobs` table and `jobs/worker.py` runs it, with retries and backoff.
  Register handlers with `@jobs.handlers.handler("<kind>")`. Don't add
  Celery, RQ or a broker; we chose a DB queue to avoid running one.
- Job handlers must be safe to run more than once (the worker retries on any
  exception, and a crash after the side effect but before `mark_done` re-runs
  it). Use `dedupe_key` on enqueue to avoid duplicate jobs.
- Schema changes are numbered SQL files in `migrations/`.
- Tests use an in-memory SQLite database via `tests/base.py`.
