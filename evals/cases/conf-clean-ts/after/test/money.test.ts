import { test } from "node:test";
import assert from "node:assert/strict";
import { subtotalCents } from "../src/cart/money.ts";

test("subtotalCents sums line items and ignores shipping", () => {
  assert.equal(subtotalCents([]), 0);
  assert.equal(subtotalCents([{ sku: "a", qty: 2, unitCents: 150 }, { sku: "b", qty: 1, unitCents: 1 }]), 301);
});
