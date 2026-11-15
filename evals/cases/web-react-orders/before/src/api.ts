export interface Order {
  id: string;
  customer: string;
  status: "pending" | "paid" | "shipped" | "refunded";
  totalCents: number;
  createdAt: string; // ISO 8601
}

/** GET /api/orders: every open order for the warehouse, typically 5k–20k rows. */
export async function fetchOrders(): Promise<Order[]> {
  const res = await fetch("/api/orders");
  if (!res.ok) throw new Error(`orders: ${res.status}`);
  return res.json();
}

export const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
