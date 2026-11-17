# Plan: Payment provider webhooks → ledger

**Status:** Accepted
**Date:** 2026-11-08
**Scope:** Accept signed webhooks from the payment provider and forward each event to the internal ledger once.

## Goal
Every payment event the provider sends reaches the ledger exactly once, and forged requests are rejected cheaply.

## Requirements
- R1: Reject requests whose signature doesn't match, before doing any other work.
- R2: Forward each event to the ledger; survive brief ledger outages.
- R3: Don't forward the same event twice (the provider redelivers).
- R4: Don't hammer the ledger with retries for requests it will never accept.
**Non-goals:** replaying historical events, an admin UI.

## Current state
- Config in `hooks/config.py:3` (`WEBHOOK_SECRET`, `LEDGER_URL`).
- Logging goes through `hooks/log.py:15` `get_logger`.
- `hooks/dedupe.py:1` `SeenEvents.add_if_new(event_id)` for idempotency.

## Decisions
- **D1:** Verify `X-Signature` as hex HMAC-SHA256 of the **raw request body** with `WEBHOOK_SECRET`, compared with `hmac.compare_digest`, **before** parsing the JSON. *Why:* R1; parsing attacker-controlled JSON before authenticating it is wasted work and attack surface, and re-serialized JSON wouldn't match the signature anyway. *Rejected:* verifying after parsing.
- **D2:** Forward with retries: exponential backoff (0.5 s, 1 s, 2 s, 4 s), **at most 5 attempts**, and retry **only** on HTTP 5xx and timeouts/connection errors. A 4xx from the ledger is permanent: log it and stop. *Why:* R2 and R4. *Rejected:* fixed delay (synchronized retries during an outage); retrying everything (4xx never succeeds).
- **D3:** Dedupe on the provider's `id` field with `SeenEvents.add_if_new` before forwarding; a duplicate returns 200 without forwarding. *Why:* R3.
- **D4:** The ledger client takes an injectable `send(url, body) -> int` and `sleep` so tests need no network.

## Design
### Components
| Component | Path | New/changed | Responsibility |
|---|---|---|---|
| Signature check | `hooks/signature.py` | New | `verify(raw_body, header) -> bool` |
| Receiver | `hooks/receiver.py` | New | `handle(raw_body, headers) -> int` status code |
| Ledger client | `hooks/ledger.py` | New | `forward(event)` with D2 retries |
### Flow and failure handling
1. `handle` reads the raw body and `X-Signature`; bad or missing signature → 401, nothing parsed.
2. Parse JSON; malformed → 400.
3. Duplicate `id` → 200, not forwarded.
4. `forward(event)`; success → 200. Retries exhausted → 502 so the provider redelivers later. 4xx from ledger → log and 200 (don't make the provider retry a permanent failure).

## Implementation steps
1. `hooks/signature.py` (D1). *Done when:* valid/invalid signature tests pass.
2. `hooks/ledger.py` (D2, D4). *Done when:* retry tests pass with a fake `send`.
3. `hooks/receiver.py` (D1, D3). *Done when:* flow tests pass.

## Test plan
- Signature: valid, tampered body, missing header.
- Ledger: 503 then 200 retries; 400 doesn't retry; gives up after 5 attempts; backoff doubles.
- Receiver: forged request rejected without parsing; duplicate not forwarded.

## Deviation log
