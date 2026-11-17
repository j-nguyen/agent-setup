CREATE TABLE IF NOT EXISTS coupons (
    code             TEXT PRIMARY KEY,
    percent_off      INTEGER NOT NULL CHECK (percent_off BETWEEN 1 AND 100),
    expires_at       TEXT NOT NULL,
    max_redemptions  INTEGER NOT NULL CHECK (max_redemptions > 0),
    redeemed_count   INTEGER NOT NULL DEFAULT 0
);
