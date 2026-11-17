export interface LineItem {
  sku: string;
  qty: number;
  unitCents: number;
}

export interface Cart {
  readonly items: readonly LineItem[];
  readonly shippingCents: number;
}
