CREATE TABLE accounts (
    id          bigserial PRIMARY KEY,
    email       text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now()
);
