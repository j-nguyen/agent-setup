CREATE TABLE subscriptions (
    id           bigserial PRIMARY KEY,
    plan_id      bigint NOT NULL REFERENCES plans(id),
    account_id   bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    started_at   timestamptz NOT NULL DEFAULT now(),
    canceled_at  timestamptz,
    status       text DEFAULT 'active'
);
