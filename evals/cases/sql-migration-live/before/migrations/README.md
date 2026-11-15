# Migrations

Production: PostgreSQL 16. `orders` has ~80M rows and `order_items` ~400M. Both
are written to constantly, 24/7. A migration may not block writes to either
table for more than a few seconds. Migrations run during normal traffic via
`runner.py` (one transaction per file).
