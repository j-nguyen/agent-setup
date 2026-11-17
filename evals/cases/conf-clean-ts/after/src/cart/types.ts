export interface LineItem {
  sku: string;
  qty: number;
  unitCents: number;
}

export interface Cart {
  readonly items: readonly LineItem[];
  readonly shippingCents: number;
  readonly couponCode?: string;
  readonly discountCents?: number;
}

export interface Coupon {
  code: string;
  percent: number;
  expiresAt: Date;
  minSubtotalCents?: number;
  maxDiscountCents?: number;
}
