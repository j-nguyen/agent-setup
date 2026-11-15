After an invoice is finalized, email it to the customer and book it in the accounting ledger, in the background.

1. `InvoiceFinalizer#call` stays fast. The email and the ledger sync run as Sidekiq jobs (Sidekiq 8).
2. The jobs must only see committed data. If finalizing fails or rolls back, nothing gets emailed or booked.
3. Sidekiq retries failed jobs, so both jobs must be safe to run more than once. A customer must never get the same invoice email twice, and an invoice is booked in the ledger once.
4. The ledger entry's `booked_at` is the invoice's `finalized_at`.
5. Jobs must actually be processed by our Sidekiq deployment (`config/sidekiq.yml`).
