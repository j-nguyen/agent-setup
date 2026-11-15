/** GET /api/products?q=…; resolves to [{ id, name, price, imageUrl, imageWidth, imageHeight }]. Up to 500 results. */
export async function searchProducts(query, { signal } = {}) {
  const res = await fetch(`/api/products?q=${encodeURIComponent(query)}`, { signal });
  if (!res.ok) throw new Error(`search failed: ${res.status}`);
  return res.json();
}

export function formatPrice(cents) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
}
