from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class LineItem:
    sku: str
    unit_price: Decimal
    qty: int


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def invoice_total(items: list[LineItem]) -> Decimal:
    """Sum of unit_price * qty over all lines."""
    return _round(sum((i.unit_price * i.qty for i in items), Decimal("0")))
