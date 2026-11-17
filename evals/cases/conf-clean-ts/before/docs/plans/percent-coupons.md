# Plan: Percent-off coupons

**Status:** Accepted
**Date:** 2026-11-04
**Scope:** Let a cart carry one percent-off coupon and reflect it in the total.

## Goal
Marketing wants percent-off coupon codes (e.g. `FALL15`) with an expiry, an optional
minimum subtotal and an optional cap, applied in the pure cart module.

## Requirements
- R1: A cart can have at most one coupon applied.
- R2: Unknown, expired and below-minimum coupons are rejected with a distinguishable reason.
- R3: Discount is a percentage of the item subtotal (not shipping), rounded down to the cent, capped when the coupon has a cap.
- R4: The total never goes below zero.
**Non-goals:** stacking coupons; fixed-amount coupons; storing coupons in a database.
**Assumptions:** the coupon list is small and ships with the code.

## Current state
- `src/cart/total.ts:3` computes the total inline (items + shipping).
- `src/cart/types.ts:6` `Cart` is a readonly value object; the module has no I/O.

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A. Discount computed in `cartTotal` from a code | `cartTotal(cart, code)` | Few changes | Mixes validation into totals; every caller passes the code |
| B. `applyCoupon` returns a new cart with `coupon` + `discountCents` | Pure function, total reads the field | Validation in one place; cart stays immutable | One more field on `Cart` |
**Chosen:** B, because it keeps validation separate and the cart immutable.

## Decisions
- **D1:** Coupons are a static `COUPONS` map in `src/cart/couponCatalog.ts`. *Why:* small list, no I/O in this module. *Rejected:* a database table (non-goal).
- **D2:** `applyCoupon(cart, code, now)` is pure: it returns a new `Cart` with `couponCode` and `discountCents` set and never mutates its input. Applying a second coupon replaces the first. *Why:* R1 and the existing immutable style.
- **D3:** Rejections throw `CouponError` with `reason: "unknown" | "expired" | "min_not_met"`. *Why:* R2; callers map reasons to messages.
- **D4:** `discountCents = Math.floor(subtotal * percent / 100)`, then `Math.min(discount, maxDiscountCents)` when a cap is set. *Why:* R3; rounding down never over-discounts.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Catalog | `src/cart/couponCatalog.ts` | new | `COUPONS: ReadonlyMap<string, Coupon>` |
| Coupons | `src/cart/coupons.ts` | new | `applyCoupon`, `CouponError` |
| Types | `src/cart/types.ts` | changed | optional `couponCode`, `discountCents` on `Cart`; `Coupon` type |
| Total | `src/cart/total.ts` | changed | subtract `discountCents`, clamp at 0 |
### Boundaries
- `src/cart/**` stays pure: no imports from `src/http`, no I/O, no `Date.now()` (time is passed in).
### Interfaces
```ts
interface Coupon { code: string; percent: number; expiresAt: Date; minSubtotalCents?: number; maxDiscountCents?: number }
function applyCoupon(cart: Cart, code: string, now: Date): Cart
class CouponError extends Error { reason: "unknown" | "expired" | "min_not_met" }
```
Codes are matched case-insensitively. A coupon is expired when `now >= expiresAt`.

## Implementation steps
1. Catalog and types: `couponCatalog.ts`, `types.ts`. *Done when:* types compile and `COUPONS` has the launch codes.
2. `applyCoupon` + `CouponError`: `coupons.ts`. *Done when:* unit tests for each reason pass.
3. Total: `total.ts`. *Done when:* totals subtract the discount and never go negative.
4. Tests: `test/coupons.test.ts`. *Done when:* the test plan passes.

## Test plan
- Unit: each rejection reason; floor rounding; cap; input cart not mutated; total clamps at 0.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Clock skew between servers around expiry | Low | expiry compares against the passed-in `now` |

## Conformance checklist
- [ ] C1: `COUPONS` is a static map in `src/cart/couponCatalog.ts` with no I/O (D1, step 1)
- [ ] C2: `applyCoupon(cart, code, now)` returns a new cart and never mutates the input; a second coupon replaces the first (D2, step 2)
- [ ] C3: Unknown, expired (`now >= expiresAt`) and below-minimum coupons throw `CouponError` with reasons `unknown`, `expired`, `min_not_met`; codes match case-insensitively (D3, step 2)
- [ ] C4: Discount is `Math.floor(subtotal * percent / 100)` on items only, capped at `maxDiscountCents` when set (D4, step 2)
- [ ] C5: `cartTotal` subtracts `discountCents` and never returns less than 0 (D2, step 3)
- [ ] C6: `src/cart/**` has no `src/http` imports, no I/O and no `Date.now()` (boundary)
- [ ] C7: Tests cover each reason, floor rounding, the cap, non-mutation and the clamp (step 4)

## Deviation log
