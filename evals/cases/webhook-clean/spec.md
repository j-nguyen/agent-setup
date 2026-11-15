Receive billing webhooks from the payment provider.

1. `POST /webhooks/billing` accepts events signed with the header `X-Billing-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw request body>">`. Return 400 when the signature is missing or invalid, or the timestamp is more than 5 minutes off.
2. Secret rotation: `WEBHOOK_SECRETS` holds comma-separated secrets, and a signature from any of them is accepted. The header may carry several `v1` entries.
3. Apply each event id exactly once, even when the provider redelivers it. If applying fails, return 500 so the provider retries later.
4. Handle `invoice.paid` and `customer.subscription.deleted`. Acknowledge other event types with 200 and ignore them.
5. The admin webhook log page shows recent payloads with the search term highlighted.
