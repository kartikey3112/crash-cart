import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.data import GENERAL_ITEM, PREMIUM_ITEM
from tests.api.pricing_oracle import expected_totals
from tests.api.schemas import Cart

pytestmark = [pytest.mark.api, pytest.mark.feature("coupons")]


@pytest.mark.bug("cart_rounding")
@pytest.mark.parametrize(
    ("code", "coupon"),
    [("SAVE10", ("percent", 10)), ("FLAT5", ("fixed", 500))],
    ids=["percent", "fixed"],
)
def test_coupon_discount_follows_pricing_rules(customer, catalog, code, coupon):
    """An applied coupon's discount, tax and total match the independently calculated values."""
    customer.add_to_cart(catalog[PREMIUM_ITEM]["id"], 1)
    cart = expect_json(customer.apply_coupon(code), 200, Cart)
    assert cart.coupon_code == code
    expected = expected_totals([(catalog[PREMIUM_ITEM]["price_cents"], 1)], coupon)
    assert cart.totals.model_dump() == expected


def test_coupon_code_is_case_insensitive(customer, product_id):
    """'save10' is accepted as SAVE10."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    assert expect_json(customer.apply_coupon("  save10 "), 200, Cart).coupon_code == "SAVE10"


@pytest.mark.parametrize(
    ("code", "status", "error"),
    [
        ("NOSUCHCODE", 404, "coupon_not_found"),
        ("USEDUP", 422, "coupon_used_up"),
        ("FLAT5", 422, "coupon_min_subtotal"),  # needs $20; cart holds $9.99
        ("BIGSPEND20", 422, "coupon_min_subtotal"),  # needs $100
    ],
    ids=["unknown", "used-up", "below-min-fixed", "below-min-percent"],
)
def test_invalid_coupons_are_rejected_with_reason(customer, product_id, code, status, error):
    """Unknown, used-up and below-minimum coupons are each rejected with a specific code."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    expect_error(customer.apply_coupon(code), status, error)


@pytest.mark.bug("coupon_expiry_ignored")
def test_expired_coupon_is_rejected(customer, product_id):
    """An expired coupon is refused with coupon_expired and no discount is applied."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    expect_error(customer.apply_coupon("EXPIRED15"), 422, "coupon_expired")
    assert expect_json(customer.cart(), 200, Cart).totals.discount_cents == 0


def test_min_subtotal_boundary(customer, product_id):
    """FLAT5 needs a $20.00 subtotal: $19.98 is refused, $29.97 qualifies."""
    pid = product_id(GENERAL_ITEM)
    customer.add_to_cart(pid, 2)  # $19.98
    expect_error(customer.apply_coupon("FLAT5"), 422, "coupon_min_subtotal")
    customer.update_cart_item(pid, 3)  # $29.97
    expect_status(customer.apply_coupon("FLAT5"), 200)


def test_second_coupon_replaces_first(customer, product_id):
    """Only one coupon applies at a time; applying another replaces it."""
    customer.add_to_cart(product_id(PREMIUM_ITEM), 1)
    customer.apply_coupon("SAVE10")
    cart = expect_json(customer.apply_coupon("FLAT5"), 200, Cart)
    assert (cart.coupon_code, cart.totals.discount_cents) == ("FLAT5", 500)


def test_remove_coupon_is_idempotent(customer, product_id):
    """DELETE /cart/coupon removes the coupon and can safely be repeated."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    customer.apply_coupon("SAVE10")
    expect_status(customer.remove_coupon(), 204)
    expect_status(customer.remove_coupon(), 204)
    assert expect_json(customer.cart(), 200, Cart).coupon_code is None


def test_coupon_stops_applying_when_cart_drops_below_minimum(customer, product_id):
    """If the subtotal falls below a coupon's minimum, the discount disappears from the totals."""
    pid = product_id(GENERAL_ITEM)
    customer.add_to_cart(pid, 3)  # $29.97
    customer.apply_coupon("FLAT5")
    cart = expect_json(customer.update_cart_item(pid, 1), 200, Cart)  # $9.99
    assert cart.totals.discount_cents == 0
