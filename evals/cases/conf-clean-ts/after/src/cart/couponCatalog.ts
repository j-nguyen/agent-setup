import type { Coupon } from "./types.ts";

const LAUNCH_COUPONS: Coupon[] = [
  { code: "FALL15", percent: 15, expiresAt: new Date("2026-12-01T00:00:00Z") },
  { code: "BIGSPEND20", percent: 20, expiresAt: new Date("2027-01-15T00:00:00Z"),
    minSubtotalCents: 10_000, maxDiscountCents: 5_000 },
  { code: "WELCOME10", percent: 10, expiresAt: new Date("2027-06-30T00:00:00Z"), maxDiscountCents: 2_000 },
];

export const COUPONS: ReadonlyMap<string, Coupon> = new Map(
  LAUNCH_COUPONS.map((c) => [c.code.toUpperCase(), c]),
);
