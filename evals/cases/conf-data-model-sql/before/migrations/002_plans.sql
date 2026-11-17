CREATE TABLE plans (
    id            bigserial PRIMARY KEY,
    code          text NOT NULL UNIQUE,
    monthly_cents integer NOT NULL CHECK (monthly_cents >= 0)
);
