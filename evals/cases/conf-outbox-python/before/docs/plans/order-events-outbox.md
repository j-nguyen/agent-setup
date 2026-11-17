# Plan: Order-created events via a transactional outbox

**Status:** Accepted
**Date:** 2026-11-02
**Scope:** Publish an `order.created` event for every committed order, reliably.

## Goal
Downstream services (fulfilment, analytics) need an `order.created` event for every
order that is committed, and never for an order that rolled back.

## Requirements
- R1: Every committed order produces exactly one `order.created` event (at-least-once delivery is acceptable; consumers dedupe on `order_id`).
- R2: A rolled-back order never produces an event.
- R3: A broker outage must not fail or slow down order creation.
**Non-goals:** replaying historical events; changing the payload of existing events.
**Assumptions:** a single relay process; volume under 50 orders/second.

## Current state
- `shop/orders.py:17` `create_order` writes the order and items in one `with conn:` transaction.
- `shop/broker.py:15` `Broker.publish` is a network call that raises `PublishError`.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A. Publish after commit | Call `broker.publish` after the `with conn:` block | Simple | Event lost if the process dies between commit and publish |
| B. Publish inside the transaction | Call `broker.publish` inside `with conn:` | Simple | Event sent for orders that later roll back; broker latency holds the transaction open; outage fails orders |
| C. Transactional outbox | Write an outbox row in the order transaction; a relay publishes it | Atomic with the order; broker outage only delays events | One more table and a relay loop |
**Chosen:** C, because it is the only option that satisfies R1–R3 together.

## Decisions
- **D1:** Write the event to an `outbox_events` table in the same transaction as the order. *Why:* atomicity with the order (R1, R2). *Rejected:* B (sends events for rolled-back orders, couples order latency to the broker).
- **D2:** A relay function publishes unsent rows in `id` order, in batches, and sets `sent_at` only after `publish` returns. *Why:* at-least-once delivery, ordered per relay. *Rejected:* deleting rows on publish (loses the audit trail).
- **D3:** Order creation never talks to the broker. *Why:* R3; keeps the broker out of the request path.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Schema | `shop/db.py` | changed | add `outbox_events` |
| Order creation | `shop/orders.py` | changed | insert the outbox row inside the order transaction |
| Relay | `shop/outbox_relay.py` (or similar name) | new | `relay_pending(conn, broker, batch_size=100) -> int` |
### Boundaries
- `shop/orders.py` must not import `shop.broker` or receive a broker object.
- Only the relay calls `Broker.publish` for order events.
### Data model
`outbox_events(id INTEGER PK AUTOINCREMENT, topic TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT now, sent_at TEXT NULL)`.
Payload: `{"order_id", "customer_id", "total_cents"}` as JSON.
### Flow and failure handling
1. `create_order` inserts order, items and one outbox row (`topic = "order.created"`) in one transaction.
2. The relay selects up to `batch_size` rows with `sent_at IS NULL` ordered by `id`.
3. For each row it calls `broker.publish`; on success it sets `sent_at`. On `PublishError` it stops the batch and leaves the row unsent for the next run.

## Implementation steps
1. Add `outbox_events` to the schema: `shop/db.py`. *Done when:* the table exists after `connect()`.
2. Insert the outbox row in `create_order`: `shop/orders.py`. *Done when:* a committed order has exactly one outbox row; a failed one has none.
3. Add the relay: new relay module. *Done when:* pending rows are published once and marked sent.
4. Tests: `tests/`. *Done when:* the test plan passes.

## Test plan
- Unit: a rolled-back order leaves no outbox row.
- Unit: the relay publishes pending rows in order and marks them sent.
- Unit: a publish failure leaves the row unsent.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Relay falls behind | Low | batch size config; alert on oldest unsent row age |

## Conformance checklist
- [ ] C1: `outbox_events` exists with `id`, `topic`, `payload`, `created_at`, `sent_at` (D1, step 1)
- [ ] C2: `create_order` inserts exactly one `order.created` outbox row inside the same transaction as the order (D1, step 2)
- [ ] C3: `shop/orders.py` never imports or calls the broker; order creation does not depend on broker availability (D3, step 2)
- [ ] C4: The relay publishes rows with `sent_at IS NULL` in `id` order, at most `batch_size` per call, and sets `sent_at` only after a successful publish (D2, step 3)
- [ ] C5: On `PublishError` the relay stops and leaves the row unsent (D2, step 3)
- [ ] C6: Tests cover rollback-leaves-no-row, relay-marks-sent and failure-leaves-unsent (step 4)

## Deviation log
