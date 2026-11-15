Rework checkout so it holds database locks briefly and never loses or duplicates side effects (SQLAlchemy 2.0, PostgreSQL 16).

1. Hundreds of concurrent checkouts hit the same hot products. Product row locks must be held only for the stock reservation, never while calling the payment provider (1–30 s).
2. A checkout is charged at most once, even when the client retries it with the same `checkout_id`.
3. A declined card releases the reserved stock.
4. Every paid order publishes exactly one `orders.paid` event to the broker (consumers dedupe on `event_id`, so at-least-once delivery is fine). No event may be published for an order that didn't commit, and none may be lost if the process crashes.
5. Loyalty points are best effort. A failure awarding them must not affect the order.
6. Deadlocks and serialization failures are retried transparently.
7. Orders left `pending` by a crash are completed or cancelled within 1 hour by the existing `reconcile_pending_orders` job (well inside the provider's 24 h idempotency window), and sent outbox rows are deleted by the existing `prune_outbox` job (both out of scope).
