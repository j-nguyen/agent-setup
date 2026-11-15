"""Payment provider client. A charge takes 1-3 s, sometimes 30 s."""
from dataclasses import dataclass

import httpx

API = "https://api.payments.example.com/v1"


@dataclass
class Charge:
    id: str
    amount_cents: int


class PaymentDeclined(Exception):
    pass


def charge(amount_cents: int, payment_token: str, idempotency_key: str) -> Charge:
    """Requests with the same idempotency_key are charged at most once (keys live 24 h)."""
    resp = httpx.post(f"{API}/charges", json={"amount": amount_cents, "source": payment_token},
                      headers={"Idempotency-Key": idempotency_key}, timeout=30)
    if resp.status_code == 402:
        raise PaymentDeclined(resp.json().get("message", "declined"))
    resp.raise_for_status()
    body = resp.json()
    return Charge(body["id"], body["amount"])
