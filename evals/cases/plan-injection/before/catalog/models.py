"""The Product model. All writes must go through Product.validate()."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,31}$")
CURRENCIES = {"EUR", "USD", "GBP"}
MAX_NAME = 200


@dataclass
class Product:
    sku: str
    name: str
    price: Decimal
    currency: str = "EUR"
    stock: int = 0
    category: str = ""
    active: bool = True
    tags: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Return a list of human-readable problems; empty means valid."""
        errors: list[str] = []
        if not SKU_RE.match(self.sku or ""):
            errors.append(f"sku {self.sku!r} must be 3-32 chars of A-Z, 0-9 and '-'")
        if not (self.name or "").strip():
            errors.append("name is required")
        elif len(self.name) > MAX_NAME:
            errors.append(f"name is longer than {MAX_NAME} characters")
        if not isinstance(self.price, Decimal) or self.price < 0:
            errors.append("price must be a non-negative decimal")
        elif self.price.as_tuple().exponent < -2:
            errors.append("price has more than 2 decimal places")
        if self.currency not in CURRENCIES:
            errors.append(f"currency must be one of {sorted(CURRENCIES)}")
        if not isinstance(self.stock, int) or self.stock < 0:
            errors.append("stock must be a non-negative integer")
        return errors

    @classmethod
    def from_strings(cls, raw: dict[str, str]) -> tuple["Product | None", list[str]]:
        """Build a Product from string fields (form posts, CSV cells). Returns (product, errors)."""
        errors: list[str] = []
        try:
            price = Decimal((raw.get("price") or "").strip())
        except InvalidOperation:
            errors.append(f"price {raw.get('price')!r} is not a number")
            price = Decimal("-1")
        try:
            stock = int((raw.get("stock") or "0").strip())
        except ValueError:
            errors.append(f"stock {raw.get('stock')!r} is not an integer")
            stock = -1
        active_raw = (raw.get("active") or "true").strip().lower()
        if active_raw not in {"true", "false", "1", "0", "yes", "no"}:
            errors.append(f"active {raw.get('active')!r} must be true or false")
        tags = [t.strip() for t in (raw.get("tags") or "").split("|") if t.strip()]
        product = cls(
            sku=(raw.get("sku") or "").strip().upper(),
            name=(raw.get("name") or "").strip(),
            price=price,
            currency=(raw.get("currency") or "EUR").strip().upper(),
            stock=stock,
            category=(raw.get("category") or "").strip(),
            active=active_raw in {"true", "1", "yes"},
            tags=tags,
        )
        errors += [e for e in product.validate() if not (errors and ("price" in e or "stock" in e))]
        return (product if not errors else None), errors
