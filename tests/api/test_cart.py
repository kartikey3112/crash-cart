import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.data import GENERAL_ITEM, LOW_STOCK_ITEM, OUT_OF_STOCK_ITEM, PREMIUM_ITEM
from tests.api.pricing_oracle import expected_totals
from tests.api.schemas import Cart

pytestmark = [pytest.mark.api, pytest.mark.feature("cart")]


def test_cart_requires_login(anon):
    """The cart is private: anonymous requests get 401."""
    expect_error(anon.cart(), 401, "not_authenticated")


def test_new_customer_has_empty_cart(customer):
    """A brand-new customer's cart is empty with all totals at zero."""
    cart = expect_json(customer.cart(), 200, Cart)
    assert cart.items == [] and cart.totals.total_cents == 0 and cart.coupon_code is None


def test_add_item_returns_cart_with_line(customer, product_id):
    """Adding a product returns the updated cart with a correct line total."""
    cart = expect_json(customer.add_to_cart(product_id(GENERAL_ITEM), 2), 200, Cart)
    [line] = cart.items
    assert (line.sku, line.quantity, line.line_total_cents) == (GENERAL_ITEM, 2, 2 * 999)


def test_adding_same_product_twice_increments_quantity(customer, product_id):
    """Adding a product already in the cart increases its quantity instead of adding a line."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    cart = expect_json(customer.add_to_cart(product_id(GENERAL_ITEM), 3), 200, Cart)
    assert [(line.sku, line.quantity) for line in cart.items] == [(GENERAL_ITEM, 4)]


@pytest.mark.bug("cart_rounding")
@pytest.mark.parametrize(
    "lines",
    [
        [(GENERAL_ITEM, 1)],  # $9.99: tax 79.92c rounds up; shipping charged
        [(GENERAL_ITEM, 3)],  # $29.97: tax 239.76c
        [(PREMIUM_ITEM, 1), (GENERAL_ITEM, 1)],  # $59.98: free shipping, tax 479.84c
    ],
    ids=["one-cable", "three-cables", "earbuds-and-cable"],
)
def test_cart_totals_follow_pricing_rules(customer, catalog, lines):
    """Cart totals equal the independently calculated subtotal, 8% tax (half-up) and shipping."""
    for sku, qty in lines:
        expect_status(customer.add_to_cart(catalog[sku]["id"], qty), 200)
    cart = expect_json(customer.cart(), 200, Cart)
    expected = expected_totals([(catalog[sku]["price_cents"], qty) for sku, qty in lines])
    assert cart.totals.model_dump() == expected


def test_update_quantity(customer, product_id):
    """PATCH sets the quantity, and the line total follows."""
    pid = product_id(GENERAL_ITEM)
    customer.add_to_cart(pid, 1)
    cart = expect_json(customer.update_cart_item(pid, 5), 200, Cart)
    assert cart.items[0].quantity == 5 and cart.items[0].line_total_cents == 5 * 999


def test_update_item_not_in_cart_is_404(customer, product_id):
    """Updating a product that isn't in the cart is a 404."""
    expect_error(customer.update_cart_item(product_id(GENERAL_ITEM), 2), 404, "item_not_in_cart")


@pytest.mark.parametrize("quantity", [0, -1, 100], ids=["zero", "negative", "above-99"])
def test_quantity_outside_1_to_99_is_422(customer, product_id, quantity):
    """Quantities outside 1-99 are rejected when adding to the cart."""
    expect_status(customer.add_to_cart(product_id(GENERAL_ITEM), quantity), 422)


@pytest.mark.bug("stock_not_enforced")
def test_quantity_up_to_stock_is_allowed_beyond_is_409(customer, anon, product_id):
    """Exactly the available stock can be added; one more is a 409 insufficient_stock."""
    pid = product_id(LOW_STOCK_ITEM)
    stock = anon.product(pid).json()["stock"]  # read live: visitors may have bought some
    assert stock >= 1, "precondition: low-stock item must still have stock"
    expect_status(customer.add_to_cart(pid, stock), 200)
    expect_error(customer.add_to_cart(pid, 1), 409, "insufficient_stock")


@pytest.mark.bug("stock_not_enforced")
def test_update_beyond_stock_is_409(customer, anon, product_id):
    """Raising a cart quantity above the available stock is a 409."""
    pid = product_id(LOW_STOCK_ITEM)
    stock = anon.product(pid).json()["stock"]
    customer.add_to_cart(pid, 1)
    expect_error(customer.update_cart_item(pid, stock + 1), 409, "insufficient_stock")


@pytest.mark.bug("stock_not_enforced")
def test_out_of_stock_product_cannot_be_added(customer, product_id):
    """A product with zero stock can't be added at all."""
    expect_error(customer.add_to_cart(product_id(OUT_OF_STOCK_ITEM), 1), 409, "insufficient_stock")


def test_unknown_product_cannot_be_added(customer):
    """Adding a non-existent product is a 404."""
    expect_error(customer.add_to_cart(999999, 1), 404, "product_not_found")


@pytest.mark.bug("remove_item_noop")
def test_remove_item(customer, product_id):
    """DELETE removes the product: the cart is empty afterwards."""
    pid = product_id(GENERAL_ITEM)
    customer.add_to_cart(pid, 2)
    expect_status(customer.remove_cart_item(pid), 204)
    assert expect_json(customer.cart(), 200, Cart).items == []


@pytest.mark.bug("remove_item_noop")
def test_remove_one_of_two_items_keeps_the_other(customer, product_id):
    """Removing one product leaves other cart lines untouched."""
    customer.add_to_cart(product_id(GENERAL_ITEM), 1)
    customer.add_to_cart(product_id(PREMIUM_ITEM), 1)
    expect_status(customer.remove_cart_item(product_id(GENERAL_ITEM)), 204)
    assert [line.sku for line in expect_json(customer.cart(), 200, Cart).items] == [PREMIUM_ITEM]


@pytest.mark.bug("remove_item_noop")
def test_remove_item_twice_is_404(customer, product_id):
    """A second DELETE for the same product is a 404 (it is no longer in the cart)."""
    pid = product_id(GENERAL_ITEM)
    customer.add_to_cart(pid, 1)
    expect_status(customer.remove_cart_item(pid), 204)
    expect_error(customer.remove_cart_item(pid), 404, "item_not_in_cart")


def test_carts_are_isolated_between_customers(new_customer, product_id):
    """One customer's cart contents are never visible to another customer."""
    alice, bob = new_customer(), new_customer()
    alice.add_to_cart(product_id(GENERAL_ITEM), 1)
    assert expect_json(bob.cart(), 200, Cart).items == []
