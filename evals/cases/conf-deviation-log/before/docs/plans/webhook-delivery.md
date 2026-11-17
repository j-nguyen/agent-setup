# Plan: Outbound webhook delivery

**Status:** Accepted
**Date:** 2026-10-30
**Scope:** Deliver signed event webhooks to customer endpoints, with retries and failure tracking.

## Goal
Customers can register an HTTPS endpoint and receive signed JSON events. Failed deliveries are
retried a few times, then recorded as failed so support can see them.

## Requirements
- R1: POST each event as JSON to the endpoint URL, signed with the endpoint's secret.
- R2: Retry transient failures; don't retry client errors.
- R3: Bound how long one delivery attempt can take.
- R4: Record the outcome of every delivery.
**Non-goals:** a delivery queue or scheduler (the caller invokes delivery), endpoint registration UI.

## Current state
- `retry()` with exponential backoff and a `shouldRetry` hook already exists (`src/lib/retry.ts:14`).
- Structured JSON logging via `createLogger` (`src/lib/logger.ts:10`).
- Config is read from env in one place, `loadConfig` (`src/config.ts:16`).

## Options considered
| Option | Summary | Pros | Cons |
|---|---|---|---|
| A | Reuse `retry()` and global `fetch` | No dependencies, matches email sender | Backoff only in-process |
| B | Add a job queue library | Durable retries | New infra, out of scope |
**Chosen:** A.

## Decisions
- **D1:** Sign with HMAC-SHA256 over the exact body bytes; header `X-Signature: sha256=<hex>`.
  Signing lives in `src/webhooks/sign.ts` as `signPayload(secret, body)`.
- **D2:** Use `retry()` with 3 attempts. Retry network errors, timeouts, 5xx, 408 and 429; never other 4xx.
- **D3:** Abort each attempt after a configurable timeout using `AbortSignal.timeout`.
- **D4:** On final failure log `warn("webhook.delivery_failed", {endpointId, eventId, attempts, status})`.
  Never log the secret or the body.
- **D5:** Outcomes go through a `DeliveryStore` interface: `markDelivered(eventId, endpointId)` and
  `markFailed(eventId, endpointId, reason)`.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Signer | `src/webhooks/sign.ts` | new | `signPayload` |
| Delivery | `src/webhooks/deliver.ts` | new | `deliverWebhook(endpoint, event, deps)` |
| Store interface | `src/webhooks/store.ts` | new | `DeliveryStore` + in-memory implementation for tests |
| Config | `src/config.ts` | changed | timeout setting |
### Interfaces
```ts
interface Endpoint { id: string; url: string; secret: string }
interface WebhookEvent { id: string; type: string; payload: unknown }
deliverWebhook(endpoint, event, { store, log, config }): Promise<"delivered" | "failed">
```
Config: env `WEBHOOK_TIMEOUT_MS` (default 5000) → `config.webhookTimeoutMs`.

## Implementation steps
1. Signer (D1): `src/webhooks/sign.ts`. *Done when:* a known vector matches.
2. Delivery with retry and timeout (D2, D3): `src/webhooks/deliver.ts`, `src/config.ts`. *Done when:* retries per D2.
3. Outcome recording and logging (D4, D5): `src/webhooks/store.ts`, `deliver.ts`. *Done when:* store updated on both paths.
4. Tests: `test/webhooks.test.ts`. *Done when:* the test plan passes.

## Test plan
- Signature header matches an independently computed HMAC.
- A 400 is not retried; a 503 then 200 is delivered.
- Final failure logs the event and marks the delivery failed, without the secret.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| In-process retries lost on restart | Medium | Accepted for v1; revisit with a queue |

## Open questions
None.

## Conformance checklist
- [ ] C1: Requests are `POST` with `Content-Type: application/json` and `X-Signature: sha256=<hex HMAC-SHA256 of the body>` (D1, step 2)
- [ ] C2: Signing is `signPayload(secret, body)` in `src/webhooks/sign.ts` (D1, step 1)
- [ ] C3: Delivery uses the existing `retry()` with 3 attempts; 4xx other than 408/429 are not retried (D2, step 2)
- [ ] C4: Each attempt is aborted after `WEBHOOK_TIMEOUT_MS` (default 5000), exposed as `config.webhookTimeoutMs` (D3, step 2)
- [ ] C5: Final failure logs `webhook.delivery_failed` with endpointId, eventId, attempts and status, and calls `markFailed`; success calls `markDelivered` (D4, D5, step 3)
- [ ] C6: Neither the secret nor the body is logged (D4, step 3)
- [ ] C7: `test/webhooks.test.ts` covers the signature, a non-retried 400, retry-then-success and the failure path (step 4)

## Deviation log
- 2026-11-04 · C3 · Use 4 attempts (the `retry()` default, `DEFAULT_ATTEMPTS`) instead of 3, to match the email sender's retry budget · accepted
