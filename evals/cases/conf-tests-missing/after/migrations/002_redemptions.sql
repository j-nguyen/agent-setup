CREATE TABLE IF NOT EXISTS redemptions (
    code         TEXT NOT NULL REFERENCES coupons (code),
    user_id      TEXT NOT NULL,
    redeemed_at  TEXT NOT NULL,
    UNIQUE (code, user_id)
);
