CREATE TABLE coupons (
  id    bigserial PRIMARY KEY,
  code  text NOT NULL UNIQUE,
  percent_off int NOT NULL
);

CREATE TABLE orders (
  id          bigserial PRIMARY KEY,
  customer_id bigint NOT NULL,
  country     char(2) NOT NULL,
  status      text,
  coupon_id   bigint,
  total_cents bigint NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
  id        bigserial PRIMARY KEY,
  order_id  bigint NOT NULL REFERENCES orders(id),
  sku       text NOT NULL,
  quantity  integer NOT NULL,
  price_cents bigint NOT NULL
);
