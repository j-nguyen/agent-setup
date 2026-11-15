Add `GET /users/<user_id>/orders` so customers can see their order history.

1. Only the logged-in user can list their own orders; admins can list anyone's. Others get 403.
2. Return 404 if the user does not exist.
3. Cursor pagination: `limit` (default 20, max 100) and `after` (the cursor returned by the previous page).
4. Sorted newest first by `created_at`; optional `sort=total` sorts by order total (highest first) instead.
5. Each order includes its line items (`sku`, `qty`, `price`).
6. Add a migration with the index(es) this endpoint needs. `orders` has ~40M rows in production and the table is live.
