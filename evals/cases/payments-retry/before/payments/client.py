"""HTTP client for the payments provider.

`transport` is anything with `post(url, json=, headers=, timeout=)` returning an
object with `.status`, `.headers` and `.json()` (a thin wrapper over httpx in
production, a fake in tests).
"""
from __future__ import annotations

import logging
import uuid

from .errors import PaymentError, TransientError

log = logging.getLogger(__name__)

BASE_URL = "https://api.payments.example.com/v1"


class PaymentsClient:
    def __init__(self, transport, api_key: str, timeout: float = 10.0):
        self.transport = transport
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self, idempotency_key: str) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Idempotency-Key": idempotency_key}

    def create_charge(self, amount_cents: int, currency: str, customer_id: str, source: str) -> dict:
        """Charge `source` (a tokenized card) and return the provider's charge object."""
        body = {"amount": amount_cents, "currency": currency, "customer": customer_id, "source": source}
        try:
            resp = self.transport.post(f"{BASE_URL}/charges", json=body,
                                       headers=self._headers(str(uuid.uuid4())), timeout=self.timeout)
        except (TimeoutError, ConnectionError) as e:
            raise TransientError(str(e)) from e
        if resp.status >= 500 or resp.status == 429:
            raise TransientError(f"provider returned {resp.status}")
        if resp.status >= 400:
            err = resp.json().get("error", {})
            raise PaymentError(resp.status, err.get("code", "unknown"), err.get("message", ""))
        charge = resp.json()
        log.info("created charge %s for customer %s", charge["id"], customer_id)
        return charge
