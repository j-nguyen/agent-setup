Database changes for regional sharding, order archiving and wholesale orders (migration 005).

1. Add `orders.region` (text, not null). Existing orders are `us`, except orders from EU countries, which are `eu`.
2. Add `orders.archived_at` (timestamptz). It's NULL for every existing order and only set when an order is archived.
3. Index `orders` for queries filtered by region and sorted by `created_at`.
4. `order_items.quantity` must hold values above 2^31.
5. `orders.coupon_id` must reference `coupons(id)`.
6. Follow `migrations/README.md`: this runs against live production tables during normal traffic.
