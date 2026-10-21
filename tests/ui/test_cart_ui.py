import pytest
from playwright.sync_api import expect

from tests.api.data import GENERAL_ITEM, LOW_STOCK_ITEM, PREMIUM_ITEM
from tests.api.pricing_oracle import expected_totals
from tests.ui.pages import CartPage, ProductPage

pytestmark = [pytest.mark.ui, pytest.mark.feature("cart")]


def test_add_to_cart_updates_badge(page, shopper, catalog):
    """Adding 2 units on the product page confirms it and shows 2 in the header badge."""
    product = ProductPage(page).open_by_id(catalog[GENERAL_ITEM]["id"])
    product.add_to_cart(2)
    expect(product.added_message).to_be_visible()
    expect(product.cart_count).to_have_text("2")


@pytest.mark.bug("cart_rounding")
def test_cart_shows_correctly_rounded_totals(page, shopper, catalog):
    """The cart summary shows subtotal, 8% tax rounded half-up, shipping and total correctly."""
    shopper.api.add_to_cart(catalog[GENERAL_ITEM]["id"], 1)
    cart = CartPage(page).open()
    expect(cart.items).to_have_count(1)
    expected = expected_totals([(catalog[GENERAL_ITEM]["price_cents"], 1)])
    assert cart.totals_cents() == expected


def test_update_quantity_updates_line_total(page, shopper, catalog):
    """Changing the quantity to 3 updates that line's total to 3 x unit price."""
    shopper.api.add_to_cart(catalog[GENERAL_ITEM]["id"], 1)
    cart = CartPage(page).open()
    cart.set_quantity(GENERAL_ITEM, 3)
    expect(cart.item(GENERAL_ITEM).get_by_test_id("cart-item-line-total")).to_have_text("$29.97")
    expect(cart.cart_count).to_have_text("3")


@pytest.mark.bug("remove_item_noop")
def test_remove_item_empties_cart(page, shopper, catalog):
    """Removing the only item shows the empty-cart message and a zero badge."""
    shopper.api.add_to_cart(catalog[GENERAL_ITEM]["id"], 1)
    cart = CartPage(page).open()
    cart.remove(GENERAL_ITEM)
    expect(cart.empty).to_be_visible()
    expect(cart.cart_count).to_have_text("0")


@pytest.mark.bug("stock_not_enforced")
def test_adding_more_than_stock_shows_error(page, shopper, setup_api, catalog):
    """Asking for one more unit than is in stock shows an 'Only N in stock' error."""
    product_id = catalog[LOW_STOCK_ITEM]["id"]
    stock = setup_api().product(product_id).json()["stock"]  # read live, not from seed
    product = ProductPage(page).open_by_id(product_id)
    product.add_to_cart(stock + 1)
    expect(product.error).to_contain_text(f"Only {stock}")
    expect(product.cart_count).to_have_text("0")


@pytest.mark.feature("coupons")
@pytest.mark.bug("cart_rounding")
def test_coupon_applies_correct_discount(page, shopper, catalog):
    """Applying SAVE10 (case-insensitive) shows the coupon and the correctly rounded discount."""
    shopper.api.add_to_cart(catalog[PREMIUM_ITEM]["id"], 1)
    cart = CartPage(page).open()
    cart.apply_coupon("save10")
    expect(cart.coupon_applied).to_have_text("SAVE10")
    expected = expected_totals([(catalog[PREMIUM_ITEM]["price_cents"], 1)], ("percent", 10))
    assert cart.totals_cents() == expected


@pytest.mark.feature("coupons")
@pytest.mark.bug("coupon_expiry_ignored")
def test_expired_coupon_shows_error(page, shopper, catalog):
    """An expired coupon shows 'This coupon has expired' and no coupon is applied."""
    shopper.api.add_to_cart(catalog[GENERAL_ITEM]["id"], 1)
    cart = CartPage(page).open()
    cart.apply_coupon("EXPIRED15")
    expect(cart.coupon_error).to_have_text("This coupon has expired")
    expect(cart.coupon_applied).to_have_count(0)
