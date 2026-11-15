import { useEffect, useState } from "react";
import { fetchOrders, type Order } from "./api";
import { OrdersTable } from "./components/OrdersTable";
import { SettingsContext } from "./SettingsContext";

export function App() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [compact, setCompact] = useState(false);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    fetchOrders().then(setOrders);
  });

  // Header clock.
  useEffect(() => {
    setInterval(() => setNow(new Date()), 1000);
  }, []);

  return (
    <SettingsContext.Provider value={{ currency: "USD", compact, setCompact }}>
      <header>
        <h1>Ops dashboard</h1>
        <time>{now.toLocaleTimeString()}</time>
        <label>
          <input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} /> Compact rows
        </label>
      </header>
      <OrdersTable orders={orders} />
    </SettingsContext.Provider>
  );
}
