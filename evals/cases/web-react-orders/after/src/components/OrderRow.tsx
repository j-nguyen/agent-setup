import { useState } from "react";
import { money, type Order } from "../api";
import { useSettings } from "../SettingsContext";

export function OrderRow({ order }: { order: Order }) {
  const { compact } = useSettings();
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr className={compact ? "row compact" : "row"} onClick={() => setExpanded(!expanded)}>
        <td>{order.id}</td>
        <td>{order.customer}</td>
        <td>{order.status}</td>
        <td>{money.format(order.totalCents / 100)}</td>
        <td>{new Date(order.createdAt).toLocaleString()}</td>
      </tr>
      {expanded && (
        <tr className="details">
          <td colSpan={5}>Order {order.id} placed by {order.customer}</td>
        </tr>
      )}
    </>
  );
}
