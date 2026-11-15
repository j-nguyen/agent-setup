import { useState } from "react";
import type { Order } from "../api";
import { OrderRow } from "./OrderRow";

type SortKey = "createdAt" | "totalCents";

export function OrdersTable({ orders }: { orders: Order[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("createdAt");
  const [filter, setFilter] = useState("");

  const visible = orders
    .sort((a, b) => (a[sortKey] < b[sortKey] ? 1 : -1))
    .filter((o) => o.customer.toLowerCase().includes(filter.toLowerCase()));

  return (
    <section>
      <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by customer" />
      <button onClick={() => setSortKey("createdAt")}>Newest</button>
      <button onClick={() => setSortKey("totalCents")}>Largest</button>
      <table>
        <tbody>
          {visible.map((order, i) => (
            <OrderRow key={i} order={order} />
          ))}
        </tbody>
      </table>
    </section>
  );
}
