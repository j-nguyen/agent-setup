"""HTTP client for the payments provider.

`transport` is anything with `post(url, json=, headers=, timeout=)` returning an
object with `.status`, `.headers` and `.json()` (a thin wrapper over httpx in
production, a fake in tests).
"""
from __future__ import annotations

import logging
import time
import uuid

from .errors import PaymentError, TransientError
from .retry import backoff_delays

log = logging.getLogger(__name__)

BASE_URL = "https://api.payments.example.com/v1"
MAX_ATTEMPTS = 3


class PaymentsClient:
    def __init__(self, transport, api_key: str, timeout: float = 10.0, max_attempts: int = MAX_ATTEMPTS,
                 sleep=time.sleep):
        self.transport = transport
        self.api_key = api_key
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.sleep = sleep

    def _headers(self, idempotency_key: str) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Idempotency-Key": idempotency_key}

    def create_charge(self, amount_cents: int, currency: str, customer_id: str, source: str) -> dict:
        """Charge `source` (a tokenized card) and return the provider's charge object.

        Timeouts, connection errors, 429 and 5xx are retried with backoff; other
        4xx raise PaymentError straight away.
        """
        body = {"amount": amount_cents, "currency": currency, "customer": customer_id, "source": source}
        reason = "no attempt made"
        for attempt, delay in enumerate(backoff_delays(self.max_attempts), start=1):
            try:
                resp = self.transport.post(f"{BASE_URL}/charges", json=body,
                                           headers=self._headers(str(uuid.uuid4())), timeout=self.timeout)
            except (TimeoutError, ConnectionError) as e:
                reason = f"{type(e).__name__}: {e}"
            else:
                if resp.status < 400:
                    charge = resp.json()
                    log.info("created charge %s for customer %s", charge["id"], customer_id)
                    return charge
                if resp.status != 429 and resp.status < 500:
                    err = resp.json().get("error", {})
                    raise PaymentError(resp.status, err.get("code", "unknown"), err.get("message", ""))
                reason = f"provider returned {resp.status}"
                retry_after = resp.headers.get("Retry-After")
                if resp.status == 429 and retry_after:
                    delay = float(retry_after) / 1000
            if attempt < self.max_attempts:
                log.warning("charge attempt %d/%d failed (%s); retrying %s", attempt, self.max_attempts,
                            reason, body)
                self.sleep(delay)
        raise TransientError(f"giving up after {self.max_attempts} attempts: {reason}")
