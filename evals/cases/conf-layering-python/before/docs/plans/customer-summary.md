# Plan: Customer spend summary and recent orders

**Status:** Accepted
**Date:** 2026-10-28
**Scope:** Two read-only customer endpoints for the support dashboard.

## Goal
Support agents need a customer's order count, total spend and last order date, plus their most
recent orders, without paging through `/orders`.

## Requirements
- R1: `GET /customers/<id>/summary` returns order count, total spend in cents and last order time.
- R2: `GET /customers/<id>/orders/recent?limit=N` returns the newest orders first.
- R3: Unknown customers return 404.
**Non-goals:** filtering by status, currency conversion, caching.
**Assumptions:** customers have at most a few hundred orders today.

## Current state
- Layering is handlers → services → storage (`README.md:5`); `app/handlers/orders.py:2` only imports services.
- `orders_repo.list_for_customer` already returns a customer's orders (`app/storage/orders_repo.py:11`).
- Errors are raised as `app.errors` types and mapped to status codes in `app/router.py:16`.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A | Summarize in the service from `list_for_customer` | No new SQL; reuses tested query | Loads every order row |
| B | New aggregate query in `orders_repo` | One row back | New SQL to maintain |
**Chosen:** A, because order counts are small and it reuses an existing, tested query.

## Decisions
- **D1:** The summary is computed in `app/services/customers.py` by loading the customer's orders with
  `orders_repo.list_for_customer` and summing them in Python. *Why:* reuse, no new SQL.
  *Rejected:* a SQL aggregate (option B), not needed at current volumes.
- **D2:** New handlers live in `app/handlers/customers.py` and call only `app/services/`. *Why:* keep
  the layering in `README.md`. *Rejected:* calling repositories from handlers for simple reads.
- **D3:** Unknown customers raise `app.errors.NotFound` from the service; the router maps it to 404.
- **D4:** `limit` defaults to 5 and is capped at 50; non-integer `limit` is a 400.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Customer service | `app/services/customers.py` | new | `customer_summary`, `recent_orders`, existence check |
| Customer handlers | `app/handlers/customers.py` | new | Parse params, call the service |
| Orders repo | `app/storage/orders_repo.py` | changed | `list_recent_for_customer(conn, customer_id, limit)` |
| Router | `app/router.py` | changed | Register the two routes |
### Boundaries
- `app/handlers/` must not import from `app/storage/`; go through `app/services/`.
- Any layer may import `app/errors.py`.
### Interfaces
```
GET /customers/<id>/summary
200 {"customer_id": 7, "order_count": 3, "total_cents": 4200, "last_order_at": "2026-01-03T09:00:00Z"}
    (order_count 0, total_cents 0, last_order_at null when the customer has no orders)
GET /customers/<id>/orders/recent?limit=5
200 {"items": [{"id", "total_cents", "status", "created_at"}, ...]}   newest first
404 {"error": "..."} for an unknown customer; 400 for a bad id or limit
```

## Implementation steps
1. Customer service with `customer_summary` (D1, D3): `app/services/customers.py`. *Done when:* unit-callable.
2. Summary handler and route (D2): `app/handlers/customers.py`, `app/router.py`. *Done when:* endpoint returns R1.
3. Recent orders: repo query, `recent_orders` service, handler, route (D2, D4). *Done when:* R2 works.
4. Tests in `tests/test_customers.py`. *Done when:* the cases in the test plan pass.

## Test plan
- Summary for a customer with orders, and with none (zeros and null).
- 404 for an unknown customer on both endpoints.
- Recent orders: newest first, default limit, cap at 50.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Customers with many orders make the summary slow | Low | Revisit with option B if needed |

## Open questions
None.

## Conformance checklist
- [ ] C1: `GET /customers/<id>/summary` returns `customer_id`, `order_count`, `total_cents`, `last_order_at`, with zeros/null for no orders (R1, step 2)
- [ ] C2: The summary is computed in `app/services/customers.py` from `orders_repo.list_for_customer`, with no new SQL (D1, step 1)
- [ ] C3: `app/handlers/customers.py` imports nothing from `app/storage/`; all data access goes through `app/services/` (D2, steps 2–3)
- [ ] C4: Unknown customers return 404 via `app.errors.NotFound` on both endpoints (D3, steps 1–3)
- [ ] C5: `limit` defaults to 5, is capped at 50, and a non-integer is a 400 (D4, step 3)
- [ ] C6: Recent orders are returned newest first in `{"items": [...]}` (R2, step 3)
- [ ] C7: `tests/test_customers.py` covers the no-orders summary, both 404s and the limit cap (step 4)

## Deviation log
