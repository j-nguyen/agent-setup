-- migrate: no-transaction
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_subscriptions_status
    ON subscriptions (status);
