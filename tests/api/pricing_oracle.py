"""An independent model of the store's pricing rules, used as the test oracle.

Written from the business rules, not copied from the backend:
  - discount: percent coupons round half-up to the cent; fixed coupons can't exceed subtotal
  - tax: 8% of (subtotal - discount), rounded half-up to the cent
  - shipping: free from $50.00 subtotal, otherwise $4.99
"""

from decimal import ROUND_HALF_UP, Decimal


def _half_up(amount: Decimal) -> int:
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def expected_totals(lines: list[tuple[int, int]], coupon: tuple[str, int] | None = None) -> dict:
    """lines: [(unit_price_cents, quantity)]; coupon: ("percent"|"fixed", value) or None."""
    subtotal = sum(price * qty for price, qty in lines)
    discount = 0
    if coupon:
        kind, value = coupon
        discount = (
            _half_up(Decimal(subtotal) * value / 100) if kind == "percent" else min(value, subtotal)
        )
    tax = _half_up(Decimal(subtotal - discount) * Decimal("0.08"))
    shipping = 0 if subtotal == 0 or subtotal >= 5000 else 499
    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "tax_cents": tax,
        "shipping_cents": shipping,
        "total_cents": subtotal - discount + tax + shipping,
    }
