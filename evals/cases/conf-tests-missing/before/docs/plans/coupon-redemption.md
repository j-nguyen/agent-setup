# Plan: Coupon redemption

**Status:** Accepted
**Date:** 2026-10-28
**Scope:** Redeeming a coupon at checkout, enforcing expiry and redemption limits.

## Goal
Let checkout redeem a coupon for a user so that a coupon is never used more often than
`max_redemptions`, never after it expires, and never twice by the same user, even under concurrent checkouts.

## Requirements
- R1: Redeeming increments `redeemed_count` and records who redeemed it.
- R2: Never exceed `max_redemptions`, even when two checkouts race for the last use.
- R3: Expired coupons can't be redeemed.
- R4: A user can redeem a given coupon only once.
**Non-goals:** Refunds and un-redeeming; stacking coupons.

## Current state
- `coupons/pricing.py:14` looks coupons up; nothing writes to `coupons` yet.
- `migrations/001_coupons.sql:1` has `redeemed_count` but no redemption records.
- `tests/helpers.py:4` gives tests an in-memory database with migrations applied.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A | `SELECT ... FOR UPDATE`, check in Python, then update | Easy to read | SQLite has no `FOR UPDATE`; two round trips |
| B | One conditional `UPDATE ... WHERE redeemed_count < max_redemptions AND expires_at > ?` | Atomic in both databases, one statement | Reason for failure needs a follow-up read |
**Chosen:** B, because it is atomic on SQLite and Postgres alike.

## Decisions
- **D1:** Redeem with one conditional `UPDATE` plus the redemption insert, in one transaction. *Why:* atomic without row locks. *Rejected:* A.
- **D2:** Enforce one redemption per user with `UNIQUE (code, user_id)` on a new `redemptions` table. *Why:* the database is the only place that sees both racing requests.
- **D3:** Failures raise distinct `CouponError` subclasses: `CouponNotFound`, `CouponExpired`, `CouponExhausted`, `CouponAlreadyRedeemed`. *Why:* checkout shows a different message for each.
- **D4:** `redeem()` takes `now` as an argument. *Why:* deterministic tests for expiry.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Migration | `migrations/002_redemptions.sql` | new | `redemptions(code, user_id, redeemed_at, UNIQUE(code, user_id))` |
| `redeem` | `coupons/redeem.py` | new | The transaction in D1 and the errors in D3 |
### Flow and failure handling
1. `UPDATE coupons SET redeemed_count = redeemed_count + 1 WHERE code = ? AND redeemed_count < max_redemptions AND expires_at > ?`.
2. If no row changed, read the coupon once to pick the error (not found / expired / exhausted), roll back and raise.
3. Insert into `redemptions`; a unique violation rolls back the whole transaction (count included) and raises `CouponAlreadyRedeemed`.

## Implementation steps
1. Migration: `migrations/002_redemptions.sql`. *Done when:* `migrate()` creates the table.
2. Redemption: `coupons/redeem.py`. *Done when:* the flow above works for all four outcomes.
3. Tests: `tests/test_redeem.py`. *Done when:* every Test plan case passes.

## Test plan
Unit tests may use `tests/helpers.memory_db()`; the race test needs a database file shared by two connections.
- Happy path: count goes up by one and a redemption row exists.
- **Race (regression for R2):** a coupon with one use left, two connections redeem it from two threads; exactly one succeeds and the other raises `CouponExhausted`; `redeemed_count` ends at `max_redemptions`.
- **Expired:** redeeming after `expires_at` raises `CouponExpired` and leaves `redeemed_count` unchanged.
- Same user twice raises `CouponAlreadyRedeemed` and the count is unchanged.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Lost update under concurrency | Medium | D1 plus the race test (C5) |

## Conformance checklist
- [ ] C1: Redemption is one conditional `UPDATE` (limit and expiry in the `WHERE`) plus the insert, in one transaction (D1, step 2)
- [ ] C2: `redemptions` has `UNIQUE (code, user_id)` (D2, step 1)
- [ ] C3: The four failures raise distinct `CouponError` subclasses, and every failure leaves `redeemed_count` unchanged (D3, step 2)
- [ ] C4: `redeem()` takes `now` as a parameter instead of reading the clock (D4, step 2)
- [ ] C5: A regression test races two connections for the last redemption and asserts exactly one succeeds (R2, step 3)
- [ ] C6: A test redeems an expired coupon and asserts `CouponExpired` with the count unchanged (R3, step 3)
- [ ] C7: Tests cover the happy path and the same-user-twice case (R1, R4, step 3)

## Deviation log
