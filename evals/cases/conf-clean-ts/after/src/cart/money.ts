import type { LineItem } from "./types.ts";

export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** Sum of qty * unit price over the line items, excluding shipping. */
export function subtotalCents(items: readonly LineItem[]): number {
  let sum = 0;
  for (const item of items) {
    sum += item.qty * item.unitCents;
  }
  return sum;
}
