CREATE TABLE users (
    id         bigserial PRIMARY KEY,
    email      text NOT NULL UNIQUE,
    name       text NOT NULL,
    is_admin   boolean NOT NULL DEFAULT false
);

CREATE TABLE orders (
    id         bigserial PRIMARY KEY,
    user_id    bigint NOT NULL REFERENCES users(id),
    total      numeric(12, 2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id       bigserial PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders(id),
    sku      text NOT NULL,
    qty      integer NOT NULL,
    price    numeric(12, 2) NOT NULL
);
