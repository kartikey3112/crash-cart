import uuid

import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.data import (
    APPROVED_CARD,
    DECLINED_CARD_NUMBER,
    EXPIRED_EXPIRY,
    GENERAL_ITEM,
    PREMIUM_ITEM,
    SHIPPING,
    STOCK_DECREMENT_ITEM,
    unique_sku,
)
from tests.api.pricing_oracle import expected_totals
from tests.api.schemas import AdminProduct, Cart, Order

pytestmark = [pytest.mark.api, pytest.mark.feature("checkout")]


def card(**changes) -> dict:
    return {**APPROVED_CARD, **changes}


def test_checkout_creates_order_and_empties_cart(customer, product_id):
    """A successful checkout returns 201 with an order and leaves the cart empty."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 2)
    order = expect_json(customer.checkout(SHIPPING, APPROVED_CARD), 201, Order)
    assert [(i.product_name, i.quantity) for i in order.items] == [("Braided USB-C Cable 2m", 2)]
    assert order.card_last4 == "4242" and order.status == "placed"
    assert expect_json(customer.cart(), 200, Cart).items == []


@pytest.mark.bug("cart_rounding")
def test_order_totals_follow_pricing_rules(customer, catalog):
    """The order is charged the independently calculated total, including a coupon."""
    customer.add_to_cart(catalog[PREMIUM_ITEM]["id"], 1)
    customer.add_to_cart(catalog[GENERAL_ITEM]["id"], 1)
    customer.apply_coupon("SAVE10")
    order = expect_json(customer.checkout(SHIPPING, APPROVED_CARD), 201, Order)
    expected = expected_totals(
        [(catalog[PREMIUM_ITEM]["price_cents"], 1), (catalog[GENERAL_ITEM]["price_cents"], 1)],
        ("percent", 10),
    )
    actual = {key: getattr(order, key) for key in expected}
    assert actual == expected
    assert order.coupon_code == "SAVE10"


def test_checkout_decrements_stock(customer, anon, product_id):
    """Buying 2 units lowers the product's stock by exactly 2."""
    pid = product_id(STOCK_DECREMENT_ITEM)
    before = anon.product(pid).json()["stock"]
    customer.add_to_cart(pid, 2)
    expect_status(customer.checkout(SHIPPING, APPROVED_CARD), 201)
    assert anon.product(pid).json()["stock"] == before - 2


def test_order_snapshots_product_details(customer, admin, catalog):
    """An order keeps the price paid even if the product's price changes later."""
    # Uses an admin-created product so changing its price can't affect other tests.
    body = {
        "sku": unique_sku(),
        "name": "API Test Snapshot",
        "category_slug": "gaming",
        "price_cents": 1234,
        "stock": 5,
    }
    pid = expect_json(admin.admin_create_product(body), 201, AdminProduct).id
    try:
        customer.add_to_cart(pid, 1)
        order = expect_json(customer.checkout(SHIPPING, APPROVED_CARD), 201, Order)
        admin.admin_update_product(pid, {"price_cents": 9999})
        refetched = expect_json(customer.order(order.id), 200, Order)
        assert refetched.items[0].unit_price_cents == 1234
    finally:
        admin.admin_delete_product(pid)


def test_checkout_with_empty_cart_is_400(customer):
    """Checking out an empty cart is a 400 cart_empty."""
    expect_error(customer.checkout(SHIPPING, APPROVED_CARD), 400, "cart_empty")


def test_checkout_requires_login(anon):
    """Anonymous checkout is 401."""
    expect_error(anon.checkout(SHIPPING, APPROVED_CARD), 401, "not_authenticated")


@pytest.mark.parametrize(
    ("changes", "status", "error"),
    [
        ({"number": "4242 4242 4242 4241"}, 422, "card_invalid"),
        ({"number": DECLINED_CARD_NUMBER}, 402, "card_declined"),
    ],
    ids=["bad-luhn", "declined"],
)
def test_card_rejections(customer, product_id, changes, status, error):
    """A card failing the Luhn check is 422; the decline test card is 402."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    expect_error(customer.checkout(SHIPPING, card(**changes)), status, error)
    assert len(expect_json(customer.cart(), 200, Cart).items) == 1, "cart must survive a failure"


@pytest.mark.bug("expired_card_accepted")
def test_expired_card_is_rejected(customer, product_id):
    """A card whose expiry month has passed is refused with card_expired and no order exists."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    expect_error(customer.checkout(SHIPPING, card(expiry=EXPIRED_EXPIRY)), 422, "card_expired")
    assert customer.orders().json() == []


@pytest.mark.parametrize(
    "field_change",
    [{"expiry": "13/30"}, {"expiry": "1/30"}, {"expiry": "01-30"}, {"cvv": "12"}, {"cvv": "1234"}],
    ids=["month-13", "one-digit-month", "dash", "cvv-short", "cvv-long"],
)
def test_malformed_card_fields_are_422(customer, product_id, field_change):
    """Expiry must be MM/YY with a real month and CVV exactly 3 digits."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    expect_status(customer.checkout(SHIPPING, card(**field_change)), 422)


@pytest.mark.parametrize(
    "missing", ["full_name", "address_line1", "city", "postal_code", "country"]
)
def test_missing_shipping_field_is_422(customer, product_id, missing):
    """Every shipping field is required."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    shipping = {k: v for k, v in SHIPPING.items() if k != missing}
    expect_status(customer.checkout(shipping, APPROVED_CARD), 422)


@pytest.mark.bug("checkout_double_submit")
def test_retry_with_same_idempotency_key_returns_original_order(customer, product_id):
    """Retrying checkout with the same Idempotency-Key returns the first order, not a duplicate."""
    key = str(uuid.uuid4())
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    first = expect_json(customer.checkout(SHIPPING, APPROVED_CARD, key), 201, Order)
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)  # a double-click after the cart refilled
    retry = customer.checkout(SHIPPING, APPROVED_CARD, key)
    assert expect_json(retry, 200, Order).id == first.id
    assert len(customer.orders().json()) == 1


def test_different_idempotency_keys_create_separate_orders(customer, product_id):
    """Two checkouts with different keys are two real orders."""
    for _ in range(2):
        customer.add_to_cart(product_id(GENERAL_ITEM), 1)
        expect_status(customer.checkout(SHIPPING, APPROVED_CARD, str(uuid.uuid4())), 201)
    assert len(customer.orders().json()) == 2


def test_idempotency_keys_are_scoped_per_customer(new_customer, product_id):
    """Two customers using the same key each get their own order."""
    key = str(uuid.uuid4())
    orders = []
    for client in (new_customer(), new_customer()):
        client.add_to_cart(product_id(GENERAL_ITEM), 1)
        orders.append(expect_json(client.checkout(SHIPPING, APPROVED_CARD, key), 201, Order).id)
    assert orders[0] != orders[1]
