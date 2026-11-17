import type { Cart, Coupon } from "./types.ts";
import { COUPONS } from "./couponCatalog.ts";
import { subtotalCents } from "./money.ts";

export type CouponRejection = "unknown" | "expired" | "min_not_met";

export class CouponError extends Error {
  readonly reason: CouponRejection;

  constructor(reason: CouponRejection, code: string) {
    super(`coupon ${code} rejected: ${reason}`);
    this.name = "CouponError";
    this.reason = reason;
  }
}

function discountFor(coupon: Coupon, subtotal: number): number {
  const raw = Math.floor((subtotal * coupon.percent) / 100);
  return coupon.maxDiscountCents === undefined ? raw : Math.min(raw, coupon.maxDiscountCents);
}

/**
 * Returns a copy of `cart` with the coupon applied. Applying a coupon to a cart
 * that already has one replaces it. Throws CouponError when the coupon can't be used.
 */
export function applyCoupon(cart: Cart, code: string, now: Date): Cart {
  const coupon = COUPONS.get(code.toUpperCase());
  if (!coupon) {
    throw new CouponError("unknown", code);
  }
  if (now.getTime() >= coupon.expiresAt.getTime()) {
    throw new CouponError("expired", code);
  }
  const itemsSubtotal = subtotalCents(cart.items);
  if (coupon.minSubtotalCents !== undefined && itemsSubtotal < coupon.minSubtotalCents) {
    throw new CouponError("min_not_met", code);
  }
  return { ...cart, couponCode: coupon.code, discountCents: discountFor(coupon, itemsSubtotal) };
}
