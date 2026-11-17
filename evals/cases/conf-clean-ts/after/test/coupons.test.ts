import { test } from "node:test";
import assert from "node:assert/strict";
import { applyCoupon, CouponError } from "../src/cart/coupons.ts";
import { cartTotal } from "../src/cart/total.ts";
import type { Cart } from "../src/cart/types.ts";

// Codes come from the launch catalog: FALL15 (15%, expires 2026-12-01),
// BIGSPEND20 (20%, min $100, cap $50), WELCOME10 (10%, cap $20).
const NOW = new Date("2026-11-10T12:00:00Z");
const cart: Cart = { items: [{ sku: "a", qty: 3, unitCents: 999 }], shippingCents: 500 };
const bigCart: Cart = { items: [{ sku: "tv", qty: 1, unitCents: 40_000 }], shippingCents: 0 };

function reason(fn: () => unknown): string {
  try {
    fn();
  } catch (e) {
    assert.ok(e instanceof CouponError);
    return e.reason;
  }
  return "no error";
}

test("rejects unknown, expired and below-minimum coupons", () => {
  assert.equal(reason(() => applyCoupon(cart, "NOPE", NOW)), "unknown");
  assert.equal(reason(() => applyCoupon(cart, "FALL15", new Date("2026-12-01T00:00:00Z"))), "expired");
  assert.equal(reason(() => applyCoupon(cart, "BIGSPEND20", NOW)), "min_not_met");
});

test("matches codes case-insensitively", () => {
  assert.equal(applyCoupon(cart, "fall15", NOW).couponCode, "FALL15");
});

test("rounds the discount down, on items only", () => {
  // 15% of 2997 = 449.55 -> 449 (shipping excluded)
  assert.equal(applyCoupon(cart, "FALL15", NOW).discountCents, 449);
});

test("caps the discount", () => {
  // 20% of 40000 = 8000, capped at 5000
  assert.equal(applyCoupon(bigCart, "BIGSPEND20", NOW).discountCents, 5000);
});

test("does not mutate the input and replaces an existing coupon", () => {
  const first = applyCoupon(cart, "FALL15", NOW);
  assert.equal(cart.discountCents, undefined);
  const second = applyCoupon(first, "WELCOME10", NOW);
  assert.equal(second.couponCode, "WELCOME10");
  assert.equal(second.discountCents, 299);
  assert.equal(first.couponCode, "FALL15");
});

test("total subtracts the discount and clamps at zero", () => {
  assert.equal(cartTotal(applyCoupon(cart, "FALL15", NOW)), 2997 + 500 - 449);
  assert.equal(cartTotal({ ...cart, discountCents: 1_000_000 }), 0);
});
