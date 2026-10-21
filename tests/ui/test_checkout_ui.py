import pytest
from playwright.sync_api import expect

from tests.api.data import APPROVED_CARD, EXPIRED_EXPIRY, GENERAL_ITEM, SHIPPING
from tests.ui.pages import CheckoutPage, OrderDetailPage, OrdersPage

pytestmark = [pytest.mark.ui, pytest.mark.feature("checkout")]


@pytest.fixture
def checkout_with_item(page, shopper, catalog) -> CheckoutPage:
    """A logged-in shopper on the checkout page with one cable in the cart."""
    shopper.api.add_to_cart(catalog[GENERAL_ITEM]["id"], 1)
    checkout = CheckoutPage(page)
    checkout.open()
    expect(checkout.root).to_be_visible()
    return checkout


def test_checkout_shows_demo_payment_banner(checkout_with_item):
    """The checkout page clearly says payments are fake before any card is entered."""
    expect(checkout_with_item.demo_banner).to_contain_text("no real payment is taken")


def test_place_order_shows_confirmation_and_history(page, checkout_with_item, shopper):
    """Placing an order confirms it at the same total, empties the cart and adds it to history."""
    total_before = checkout_with_item.total_cents()
    checkout_with_item.fill_shipping(SHIPPING)
    checkout_with_item.fill_card(APPROVED_CARD)
    checkout_with_item.place_order()

    detail = OrderDetailPage(page)
    expect(detail.confirmation).to_be_visible()
    assert detail.total_cents() == total_before
    expect(detail.cart_count).to_have_text("0")

    order_id = detail.id_from_url()
    detail.orders_link.click()
    orders = OrdersPage(page)
    expect(orders.rows).to_have_count(1)  # waits for the list to load before reading it
    assert orders.order_ids() == [order_id]


@pytest.mark.bug("expired_card_accepted")
def test_expired_card_shows_error_and_no_order(page, checkout_with_item, shopper):
    """An expired card shows 'Card has expired' and no order is created."""
    checkout_with_item.fill_shipping(SHIPPING)
    checkout_with_item.fill_card({**APPROVED_CARD, "expiry": EXPIRED_EXPIRY})
    checkout_with_item.place_order()
    expect(checkout_with_item.error).to_have_text("Card has expired")
    assert shopper.api.orders().json() == []


def test_missing_shipping_details_are_caught_in_page(checkout_with_item, shopper):
    """Submitting without shipping details shows an error in the page and sends nothing."""
    checkout_with_item.fill_card(APPROVED_CARD)
    checkout_with_item.place_order()
    expect(checkout_with_item.error).to_have_text("Please fill in every shipping field")
    assert shopper.api.orders().json() == []


# Not tagged with the checkout_double_submit bug on purpose: against the deployed store,
# network latency lets the first checkout empty the cart before the second request lands, so
# the bug can't be triggered reliably from a browser. The API test (which refills the cart
# between retries) is the reliable catcher; this test still guards the user-visible outcome.
def test_double_submit_creates_only_one_order(page, checkout_with_item, shopper):
    """Two rapid submits of the checkout form result in exactly one order."""
    checkout_with_item.fill_shipping(SHIPPING)
    checkout_with_item.fill_card(APPROVED_CARD)
    checkout_with_item.submit_twice_quickly()
    expect(OrderDetailPage(page).confirmation).to_be_visible()
    page.wait_for_load_state("networkidle")  # let the second request finish too
    assert len(shopper.api.orders().json()) == 1


def test_empty_cart_cannot_check_out(page, shopper):
    """With an empty cart the checkout page offers a link back to the shop instead of a form."""
    checkout = CheckoutPage(page)
    checkout.open()
    expect(page.get_by_test_id("checkout-empty")).to_be_visible()
    expect(checkout.place_order_button).to_have_count(0)
