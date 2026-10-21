import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.data import APPROVED_CARD, GENERAL_ITEM, SHIPPING
from tests.api.schemas import Order

pytestmark = [pytest.mark.api, pytest.mark.feature("orders")]


def place_order(client, product_id) -> Order:
    client.add_to_cart(product_id(GENERAL_ITEM), 1)
    return expect_json(client.checkout(SHIPPING, APPROVED_CARD), 201, Order)


def test_order_history_lists_own_orders_newest_first(customer, product_id):
    """GET /orders lists the customer's orders, newest first, each matching the contract."""
    first, second = place_order(customer, product_id), place_order(customer, product_id)
    response = customer.orders()
    expect_status(response, 200)
    orders = [Order.model_validate(o) for o in response.json()]
    assert [o.id for o in orders] == [second.id, first.id]


def test_order_detail_matches_checkout_response(customer, product_id):
    """GET /orders/{id} returns the same order that checkout returned."""
    placed = place_order(customer, product_id)
    assert expect_json(customer.order(placed.id), 200, Order) == placed


def test_order_history_excludes_other_customers(new_customer, product_id):
    """A customer's history never includes another customer's orders."""
    alice, bob = new_customer(), new_customer()
    place_order(alice, product_id)
    assert bob.orders().json() == []


@pytest.mark.bug("order_idor")
def test_other_customers_order_is_404(new_customer, product_id):
    """Fetching another customer's order by id is a 404, as if it didn't exist."""
    alice, bob = new_customer(), new_customer()
    order = place_order(alice, product_id)
    expect_error(bob.order(order.id), 404, "order_not_found")


def test_unknown_order_is_404(customer):
    """An order id that doesn't exist is a 404."""
    expect_error(customer.order(999999), 404, "order_not_found")


def test_orders_require_login(anon):
    """Order history is private: anonymous requests get 401."""
    expect_error(anon.orders(), 401, "not_authenticated")
