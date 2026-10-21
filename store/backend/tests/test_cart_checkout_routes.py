import pytest

from tests.helpers import APPROVED_CARD, add_to_cart, bug_headers, checkout, product_id

pytestmark = pytest.mark.unit

EXPIRED_CARD = {**APPROVED_CARD, "expiry": "01/20"}


# ---------------- cart ----------------


@pytest.mark.feature("cart")
def test_cart_requires_login(client):
    """The cart is private: no token means 401."""
    assert client.get("/cart").status_code == 401


@pytest.mark.feature("cart")
def test_cart_totals_round_half_up(client, customer):
    """A $9.99 cable: 8% tax is 79.92 cents, rounded to 80, plus $4.99 shipping."""
    totals = add_to_cart(client, customer, "PHN-003").json()["totals"]
    assert totals == {
        "subtotal_cents": 999,
        "discount_cents": 0,
        "tax_cents": 80,
        "shipping_cents": 499,
        "total_cents": 1578,
    }


@pytest.mark.feature("cart")
@pytest.mark.bug("cart_rounding")
def test_cart_rounding_bug(client, customer):
    """With the bug on, tax is truncated to 79 cents and the total is a cent short."""
    add_to_cart(client, customer, "PHN-003")
    totals = client.get("/cart", headers={**customer, **bug_headers("cart_rounding")}).json()
    assert totals["totals"]["tax_cents"] == 79
    assert totals["totals"]["total_cents"] == 1577


@pytest.mark.feature("cart")
def test_adding_same_product_increments_quantity(client, customer):
    """Adding a product that is already in the cart increases its quantity."""
    add_to_cart(client, customer, "PHN-003", 2)
    items = add_to_cart(client, customer, "PHN-003", 3).json()["items"]
    assert [(i["sku"], i["quantity"]) for i in items] == [("PHN-003", 5)]


@pytest.mark.feature("cart")
@pytest.mark.parametrize(("quantity", "status"), [(3, 200), (4, 409)])
def test_quantity_limited_by_stock(client, customer, quantity, status):
    """AUD-008 has 3 in stock: 3 can be added, 4 is a 409 conflict."""
    assert add_to_cart(client, customer, "AUD-008", quantity).status_code == status


@pytest.mark.feature("cart")
@pytest.mark.bug("stock_not_enforced")
def test_stock_not_enforced_bug(client, customer):
    """With the bug on, 4 units of a product with stock 3 can be added."""
    response = client.post(
        "/cart/items",
        json={"product_id": product_id(client, "AUD-008"), "quantity": 4},
        headers={**customer, **bug_headers("stock_not_enforced")},
    )
    assert response.status_code == 200


@pytest.mark.feature("cart")
def test_out_of_stock_product_cannot_be_added(client, customer):
    """A product with zero stock can't be added at all."""
    response = add_to_cart(client, customer, "WEA-006")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "insufficient_stock"


@pytest.mark.feature("cart")
@pytest.mark.parametrize("quantity", [0, 100])
def test_quantity_outside_1_to_99_is_rejected(client, customer, quantity):
    """Quantity must be between 1 and 99."""
    assert add_to_cart(client, customer, "PHN-003", quantity).status_code == 422


@pytest.mark.feature("cart")
def test_update_quantity(client, customer):
    """PATCH sets the quantity and the totals follow."""
    add_to_cart(client, customer, "PHN-003")
    pid = product_id(client, "PHN-003")
    body = client.patch(f"/cart/items/{pid}", json={"quantity": 4}, headers=customer).json()
    assert body["totals"]["subtotal_cents"] == 999 * 4


@pytest.mark.feature("cart")
def test_remove_item(client, customer):
    """DELETE removes the product from the cart."""
    add_to_cart(client, customer, "PHN-003")
    pid = product_id(client, "PHN-003")
    assert client.delete(f"/cart/items/{pid}", headers=customer).status_code == 204
    assert client.get("/cart", headers=customer).json()["items"] == []


@pytest.mark.feature("cart")
@pytest.mark.bug("remove_item_noop")
def test_remove_item_noop_bug(client, customer):
    """With the bug on, DELETE says 204 but the item is still in the cart."""
    add_to_cart(client, customer, "PHN-003")
    pid = product_id(client, "PHN-003")
    headers = {**customer, **bug_headers("remove_item_noop")}
    assert client.delete(f"/cart/items/{pid}", headers=headers).status_code == 204
    assert len(client.get("/cart", headers=customer).json()["items"]) == 1


@pytest.mark.feature("cart")
def test_carts_are_isolated_per_user(client, new_customer):
    """One customer's cart is invisible to another."""
    alice, bob = new_customer(), new_customer()
    add_to_cart(client, alice, "PHN-003")
    assert client.get("/cart", headers=bob).json()["items"] == []


@pytest.mark.feature("cart")
def test_update_rejects_missing_item_and_excess_stock(client, customer):
    """PATCH on a product not in the cart is 404; above stock is 409."""
    pid = product_id(client, "AUD-008")
    assert (
        client.patch(f"/cart/items/{pid}", json={"quantity": 1}, headers=customer).status_code
        == 404
    )
    add_to_cart(client, customer, "AUD-008")
    assert (
        client.patch(f"/cart/items/{pid}", json={"quantity": 4}, headers=customer).status_code
        == 409
    )


# ---------------- coupons ----------------


@pytest.mark.feature("coupons")
def test_coupon_can_be_replaced_and_removed(client, customer):
    """Applying a second coupon replaces the first; DELETE removes it (and is repeatable)."""
    add_to_cart(client, customer, "AUD-001")
    client.put("/cart/coupon", json={"code": "SAVE10"}, headers=customer)
    body = client.put("/cart/coupon", json={"code": "FLAT5"}, headers=customer).json()
    assert (body["coupon_code"], body["totals"]["discount_cents"]) == ("FLAT5", 500)
    assert client.delete("/cart/coupon", headers=customer).status_code == 204
    assert client.delete("/cart/coupon", headers=customer).status_code == 204
    assert client.get("/cart", headers=customer).json()["coupon_code"] is None


@pytest.mark.feature("coupons")
def test_percent_coupon_applies_case_insensitively(client, customer):
    """'save10' applies the SAVE10 coupon: 10% off."""
    add_to_cart(client, customer, "AUD-001")  # $49.99
    body = client.put("/cart/coupon", json={"code": "save10"}, headers=customer).json()
    assert body["coupon_code"] == "SAVE10"
    assert body["totals"]["discount_cents"] == 500  # 499.9 rounds to 500


@pytest.mark.feature("coupons")
@pytest.mark.parametrize(
    ("code", "status", "error"),
    [
        ("NOPE", 404, "coupon_not_found"),
        ("EXPIRED15", 422, "coupon_expired"),
        ("USEDUP", 422, "coupon_used_up"),
        ("FLAT5", 422, "coupon_min_subtotal"),  # needs $20, cart has $9.99
    ],
)
def test_coupon_rejections(client, customer, code, status, error):
    """Unknown, expired, used-up and below-minimum coupons are each rejected with a reason."""
    add_to_cart(client, customer, "PHN-003")
    response = client.put("/cart/coupon", json={"code": code}, headers=customer)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == error


@pytest.mark.feature("coupons")
@pytest.mark.bug("coupon_expiry_ignored")
def test_coupon_expiry_ignored_bug(client, customer):
    """With the bug on, the expired EXPIRED15 coupon is accepted."""
    add_to_cart(client, customer, "PHN-003")
    headers = {**customer, **bug_headers("coupon_expiry_ignored")}
    response = client.put("/cart/coupon", json={"code": "EXPIRED15"}, headers=headers)
    assert response.status_code == 200


# ---------------- checkout ----------------


@pytest.mark.feature("checkout")
def test_checkout_creates_order_and_empties_cart(client, customer):
    """A successful checkout returns 201, matches the cart total, empties the cart and
    reduces stock."""
    add_to_cart(client, customer, "AUD-008", 2)
    cart_total = client.get("/cart", headers=customer).json()["totals"]["total_cents"]

    response = checkout(client, customer)

    assert response.status_code == 201
    order = response.json()
    assert order["total_cents"] == cart_total
    assert order["card_last4"] == "4242"
    assert client.get("/cart", headers=customer).json()["items"] == []
    detail = client.get(f"/products/{product_id(client, 'AUD-008')}").json()
    assert detail["stock"] == 1


@pytest.mark.feature("checkout")
def test_checkout_with_empty_cart_is_400(client, customer):
    """You can't check out an empty cart."""
    response = checkout(client, customer)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "cart_empty"


@pytest.mark.feature("checkout")
@pytest.mark.parametrize(
    ("card_change", "status", "error"),
    [
        ({"number": "4242 4242 4242 4241"}, 422, "card_invalid"),
        ({"expiry": "01/20"}, 422, "card_expired"),
        ({"number": "4000 0000 0000 0002"}, 402, "card_declined"),
    ],
)
def test_checkout_card_rejections(client, customer, card_change, status, error):
    """Bad checksum, expired and declined cards are rejected with distinct codes."""
    add_to_cart(client, customer, "PHN-003")
    response = checkout(client, customer, card={**APPROVED_CARD, **card_change})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == error


@pytest.mark.feature("checkout")
@pytest.mark.parametrize("expiry", ["13/30", "1/30", "01-30"])
def test_checkout_rejects_malformed_expiry(client, customer, expiry):
    """Expiry must be MM/YY with a real month."""
    add_to_cart(client, customer, "PHN-003")
    response = checkout(client, customer, card={**APPROVED_CARD, "expiry": expiry})
    assert response.status_code == 422


@pytest.mark.feature("checkout")
@pytest.mark.bug("expired_card_accepted")
def test_expired_card_accepted_bug(client, customer):
    """With the bug on, an expired card is accepted and the order is placed."""
    add_to_cart(client, customer, "PHN-003")
    headers = {**customer, **bug_headers("expired_card_accepted")}
    assert checkout(client, headers, card=EXPIRED_CARD).status_code == 201


@pytest.mark.feature("checkout")
def test_same_idempotency_key_returns_same_order(client, customer):
    """Retrying checkout with the same Idempotency-Key returns the first order (200)."""
    add_to_cart(client, customer, "PHN-003")
    headers = {**customer, "Idempotency-Key": "key-123"}
    first = checkout(client, headers)
    retry = checkout(client, headers)
    assert (first.status_code, retry.status_code) == (201, 200)
    assert retry.json()["id"] == first.json()["id"]
    assert len(client.get("/orders", headers=customer).json()) == 1


@pytest.mark.feature("checkout")
@pytest.mark.bug("checkout_double_submit")
def test_checkout_double_submit_bug(client, customer):
    """With the bug on, a retry with the same key creates a second order."""
    headers = {**customer, "Idempotency-Key": "key-123", **bug_headers("checkout_double_submit")}
    add_to_cart(client, customer, "PHN-003")
    checkout(client, headers)
    add_to_cart(client, customer, "PHN-003")
    assert checkout(client, headers).status_code == 201
    assert len(client.get("/orders", headers=customer).json()) == 2


@pytest.mark.feature("checkout")
def test_coupon_is_used_on_checkout(client, customer):
    """A coupon applied in the cart appears on the order with the same discount."""
    add_to_cart(client, customer, "AUD-001")
    client.put("/cart/coupon", json={"code": "SAVE10"}, headers=customer)
    order = checkout(client, customer).json()
    assert (order["coupon_code"], order["discount_cents"]) == ("SAVE10", 500)


@pytest.mark.feature("checkout")
def test_checkout_fails_if_stock_sold_out_meanwhile(client, new_customer):
    """If another buyer takes the last units after you added them, checkout is a 409."""
    alice, bob = new_customer(), new_customer()
    add_to_cart(client, alice, "AUD-008", 3)
    add_to_cart(client, bob, "AUD-008", 3)
    assert checkout(client, alice).status_code == 201
    response = checkout(client, bob)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "insufficient_stock"


@pytest.mark.feature("checkout")
def test_checkout_rejects_coupon_that_stopped_qualifying(client, customer):
    """A coupon whose minimum is no longer met after a cart change blocks checkout with 422."""
    add_to_cart(client, customer, "PHN-003", 3)  # $29.97, above FLAT5's $20 minimum
    client.put("/cart/coupon", json={"code": "FLAT5"}, headers=customer)
    pid = product_id(client, "PHN-003")
    client.patch(f"/cart/items/{pid}", json={"quantity": 1}, headers=customer)  # now $9.99
    response = checkout(client, customer)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "coupon_min_subtotal"


# ---------------- orders ----------------


@pytest.mark.feature("orders")
def test_order_history_lists_own_orders(client, customer):
    """A customer sees their order in history and can open it."""
    add_to_cart(client, customer, "PHN-003")
    order_id = checkout(client, customer).json()["id"]
    assert [o["id"] for o in client.get("/orders", headers=customer).json()] == [order_id]
    assert client.get(f"/orders/{order_id}", headers=customer).status_code == 200


@pytest.mark.feature("orders")
def test_other_users_order_is_404(client, new_customer):
    """A customer can't read another customer's order: it looks like it doesn't exist."""
    alice, bob = new_customer(), new_customer()
    add_to_cart(client, alice, "PHN-003")
    order_id = checkout(client, alice).json()["id"]
    assert client.get(f"/orders/{order_id}", headers=bob).status_code == 404


@pytest.mark.feature("orders")
@pytest.mark.bug("order_idor")
def test_order_idor_bug(client, new_customer):
    """With the bug on, a customer can read another customer's order."""
    alice, bob = new_customer(), new_customer()
    add_to_cart(client, alice, "PHN-003")
    order_id = checkout(client, alice).json()["id"]
    headers = {**bob, **bug_headers("order_idor")}
    assert client.get(f"/orders/{order_id}", headers=headers).status_code == 200
