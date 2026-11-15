Retry transient failures when creating charges.

1. Retry only timeouts, connection errors, HTTP 429 and 5xx responses. Any other 4xx (e.g. 402 card declined) fails immediately with `PaymentError`.
2. At most 3 attempts in total. Exponential backoff with jitter between attempts: base 0.5 s, capped at 8 s.
3. On a 429, wait for the number of seconds in the `Retry-After` header when it is present.
4. A charge must never be created twice. The provider de-duplicates requests by `Idempotency-Key` for 24 hours, so all attempts for one charge must send the same key.
5. Log each retry at WARNING with the attempt number and the reason.
