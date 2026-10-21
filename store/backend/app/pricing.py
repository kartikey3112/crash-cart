"""Cart pricing: pure functions, no database, so they are easy to unit test.

Rule: discount and tax are rounded half-up to the nearest cent. The `cart_rounding`
bug switch truncates instead, which under-charges by a cent on most prices.
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

TAX_RATE = Decimal("0.08")
FREE_SHIPPING_THRESHOLD_CENTS = 5000
SHIPPING_CENTS = 499


@dataclass(frozen=True)
class Discount:
    kind: str  # "percent" | "fixed"
    value: int  # percent (1-100) or cents


@dataclass(frozen=True)
class Totals:
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    shipping_cents: int
    total_cents: int


def to_cents(amount: Decimal, *, truncate: bool = False) -> int:
    rounding = ROUND_DOWN if truncate else ROUND_HALF_UP
    return int(amount.quantize(Decimal("1"), rounding=rounding))


def compute_totals(
    lines: list[tuple[int, int]], discount: Discount | None = None, *, truncate: bool = False
) -> Totals:
    """lines is a list of (unit_price_cents, quantity)."""
    subtotal = sum(price * qty for price, qty in lines)
    if subtotal == 0:
        return Totals(0, 0, 0, 0, 0)

    discount_cents = 0
    if discount is not None:
        if discount.kind == "percent":
            discount_cents = to_cents(Decimal(subtotal) * discount.value / 100, truncate=truncate)
        else:
            discount_cents = min(discount.value, subtotal)

    taxable = subtotal - discount_cents
    tax_cents = to_cents(Decimal(taxable) * TAX_RATE, truncate=truncate)
    shipping_cents = 0 if subtotal >= FREE_SHIPPING_THRESHOLD_CENTS else SHIPPING_CENTS
    total = taxable + tax_cents + shipping_cents
    return Totals(subtotal, discount_cents, tax_cents, shipping_cents, total)
