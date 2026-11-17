import type { Cart } from "./types.ts";
import { subtotalCents } from "./money.ts";

export function cartTotal(cart: Cart): number {
  const gross = subtotalCents(cart.items) + cart.shippingCents;
  return Math.max(0, gross - (cart.discountCents ?? 0));
}
