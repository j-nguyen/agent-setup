"""Product storage. A thin stand-in for the Postgres repository."""
from __future__ import annotations

PRODUCTS = [
    {"id": "p1", "name": "Desk lamp", "category": "home", "price_cents": 3900},
    {"id": "p2", "name": "Notebook", "category": "office", "price_cents": 450},
    {"id": "p3", "name": "Standing desk", "category": "office", "price_cents": 41900},
]


def list_products(category: str | None = None) -> list[dict]:
    return [p for p in PRODUCTS if category is None or p["category"] == category]


def get_product(product_id: str) -> dict | None:
    return next((p for p in PRODUCTS if p["id"] == product_id), None)
