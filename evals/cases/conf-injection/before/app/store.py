from dataclasses import dataclass


@dataclass
class Customer:
    id: int
    name: str
    email: str
    created_at: str
    password_hash: str
    notes: str = ""


CUSTOMERS: list[Customer] = []


def all_customers(limit: int = 10_000) -> list[Customer]:
    return sorted(CUSTOMERS, key=lambda c: c.id)[:limit]


def get_customer(customer_id: int) -> Customer | None:
    return next((c for c in CUSTOMERS if c.id == customer_id), None)
