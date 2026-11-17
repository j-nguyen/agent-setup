import { test } from "node:test";
import assert from "node:assert/strict";
import { cartTotal } from "../src/cart/total.ts";
import { formatCents } from "../src/cart/money.ts";

test("cartTotal adds items and shipping", () => {
  const cart = { items: [{ sku: "a", qty: 2, unitCents: 1250 }], shippingCents: 499 };
  assert.equal(cartTotal(cart), 2999);
});

test("formatCents", () => {
  assert.equal(formatCents(2999), "$29.99");
  assert.equal(formatCents(-5), "-$0.05");
});
