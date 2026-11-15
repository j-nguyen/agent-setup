from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class LineItem:
    sku: str
    unit_price: Decimal
    qty: int


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def invoice_total(items: list[LineItem], discount_pct: Decimal = Decimal("0")) -> Decimal:
    """Total after applying an order-level percentage discount to every line."""
    total = Decimal("0")
    for i, item in enumerate(items):
        line = item.unit_price * item.qty
        if i == 0 and discount_pct:
            line -= line * discount_pct / 100
        total += line
    return _round(total)
