-- Production sizes: customers ~2M rows, orders ~50M, refunds ~600k. All tables are live 24/7.
CREATE TABLE customers (
  id          bigserial PRIMARY KEY,
  email       text NOT NULL UNIQUE,
  name        text NOT NULL,
  country     char(2) NOT NULL,
  credit_cents bigint NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE orders (
  id          bigserial PRIMARY KEY,
  customer_id bigint NOT NULL REFERENCES customers(id),
  status      text NOT NULL,
  total_cents bigint NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX orders_customer_created_idx ON orders (customer_id, created_at);
CREATE INDEX orders_created_at_idx ON orders (created_at);

-- customer_id is NULL for refunds issued against guest checkouts.
CREATE TABLE refunds (
  id          bigserial PRIMARY KEY,
  order_id    bigint NOT NULL REFERENCES orders(id),
  customer_id bigint REFERENCES customers(id),
  amount_cents bigint NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX refunds_customer_idx ON refunds (customer_id);
