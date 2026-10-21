from decimal import Decimal

import pytest

from app.pricing import SHIPPING_CENTS, Discount, compute_totals, to_cents

pytestmark = [pytest.mark.unit, pytest.mark.feature("pricing")]


@pytest.mark.parametrize(
    ("amount", "expected"),
    [("159.92", 160), ("159.5", 160), ("159.49", 159), ("0.5", 1), ("0", 0)],
)
def test_to_cents_rounds_half_up(amount, expected):
    """Fractional cents round half-up, so .5 always rounds away from zero."""
    assert to_cents(Decimal(amount)) == expected


def test_to_cents_truncates_when_asked():
    """Truncate mode (used by the cart_rounding bug) drops the fraction instead of rounding."""
    assert to_cents(Decimal("159.92"), truncate=True) == 159


def test_empty_cart_is_all_zero():
    """An empty cart costs nothing, including no shipping charge."""
    totals = compute_totals([])
    assert (totals.subtotal_cents, totals.shipping_cents, totals.total_cents) == (0, 0, 0)


def test_tax_and_shipping_below_free_threshold():
    """A $19.99 cart pays 8% tax rounded half-up ($1.60) plus flat shipping."""
    totals = compute_totals([(1999, 1)])
    assert totals.tax_cents == 160
    assert totals.shipping_cents == SHIPPING_CENTS
    assert totals.total_cents == 1999 + 160 + SHIPPING_CENTS


def test_free_shipping_at_threshold():
    """A subtotal of exactly $50.00 qualifies for free shipping (boundary value)."""
    assert compute_totals([(2500, 2)]).shipping_cents == 0
    assert compute_totals([(4999, 1)]).shipping_cents == SHIPPING_CENTS


def test_percent_discount_is_taxed_after_discount():
    """10% off $59.99 gives $6.00 off; tax is charged on the discounted amount."""
    totals = compute_totals([(5999, 1)], Discount("percent", 10))
    assert totals.discount_cents == 600  # 599.9 rounds to 600
    assert totals.tax_cents == 432  # 8% of 5399 = 431.92
    assert totals.total_cents == 5999 - 600 + 432


def test_fixed_discount_cannot_exceed_subtotal():
    """A fixed coupon larger than the cart only reduces the subtotal to zero."""
    totals = compute_totals([(799, 1)], Discount("fixed", 1000))
    assert totals.discount_cents == 799
    assert totals.tax_cents == 0


def test_truncation_mode_undercharges():
    """With truncation, the total for a $19.99 item is one cent lower than correct."""
    correct = compute_totals([(1999, 1)])
    buggy = compute_totals([(1999, 1)], truncate=True)
    assert correct.total_cents - buggy.total_cents == 1
