-- Regional sharding prep, order archiving, and bulk-order support.
SET lock_timeout = '5s';

-- 1. Region for every order; existing orders default to 'us'.
ALTER TABLE orders ADD COLUMN region text NOT NULL DEFAULT 'us';

-- 2. When an order was archived (NULL = not archived).
ALTER TABLE orders ADD COLUMN archived_at timestamptz DEFAULT now();

-- 3. Move EU orders to the eu region.
UPDATE orders SET region = 'eu'
WHERE country IN ('AT','BE','DE','DK','ES','FI','FR','IE','IT','NL','PL','PT','SE');

-- 4. Index for region-scoped queries.
CREATE INDEX CONCURRENTLY orders_region_created_idx ON orders (region, created_at);

-- 5. Wholesale orders can exceed 2^31 units.
ALTER TABLE order_items ALTER COLUMN quantity TYPE bigint;

-- 6. Orders must reference a real coupon.
ALTER TABLE orders ADD CONSTRAINT orders_coupon_id_fkey FOREIGN KEY (coupon_id) REFERENCES coupons (id);
