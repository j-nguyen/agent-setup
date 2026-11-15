Add wallet-to-wallet transfers (Go, `database/sql` with pgx, PostgreSQL 16).

1. `Transfer` moves `amount` between two accounts atomically. It never overdraws an account and never creates or loses money, including under heavy concurrent transfers on the same accounts.
2. Use SERIALIZABLE isolation. Transient serialization conflicts must not surface to the API caller as errors.
3. Publish a `transfers` event to Kafka for every completed transfer, and only for transfers that actually committed.
4. The service has a 20-connection pool and handles thousands of transfers per second, so a transfer must never tie up a connection longer than necessary.
