import type { Cart } from "./types.ts";

export function cartTotal(cart: Cart): number {
  let sum = 0;
  for (const item of cart.items) {
    sum += item.qty * item.unitCents;
  }
  return sum + cart.shippingCents;
}
