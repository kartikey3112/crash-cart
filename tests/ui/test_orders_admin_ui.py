import pytest
from playwright.sync_api import expect

from tests.api.data import APPROVED_CARD, GENERAL_ITEM, SHIPPING, unique_sku
from tests.ui.pages import AdminPage, CatalogPage, OrderDetailPage

pytestmark = pytest.mark.ui


@pytest.mark.feature("orders")
@pytest.mark.bug("order_idor")
def test_other_customers_order_is_not_shown(page, shopper, make_shopper, catalog):
    """Opening another customer's order URL shows 'Order not found' instead of their details."""
    other = make_shopper()
    other.api.add_to_cart(catalog[GENERAL_ITEM]["id"], 1)
    their_order = other.api.checkout(SHIPPING, APPROVED_CARD).json()["id"]

    detail = OrderDetailPage(page).open_by_id(their_order)
    expect(detail.error).to_have_text("Order not found")
    expect(detail.root).to_have_count(0)


@pytest.mark.feature("admin")
def test_customer_cannot_open_admin_page(page, shopper):
    """A customer visiting /admin sees an admin-only message and no product table."""
    admin = AdminPage(page).open()
    expect(admin.forbidden).to_be_visible()
    expect(admin.table).to_have_count(0)
    expect(admin.admin_link).to_have_count(0)


@pytest.mark.feature("admin")
def test_admin_creates_product_and_shoppers_see_it(page, admin_shopper):
    """A product added in the admin page appears in the shop's search results."""
    sku, name = unique_sku(), f"UI Test Gadget {unique_sku()}"
    admin = AdminPage(page).open()
    try:
        admin.create_product(sku, name, "gaming", "12.34", 4, "Created by the UI suite.")
        expect(admin.success).to_have_text(f"Created {sku}")
        expect(admin.row(sku)).to_be_visible()

        catalog = CatalogPage(page).open(q=name)
        expect(catalog.card(sku)).to_be_visible()
        expect(catalog.card(sku).get_by_test_id("product-card-price")).to_have_text("$12.34")
    finally:
        created = [p for p in admin_shopper.api.admin_products().json() if p["sku"] == sku]
        if created:
            admin_shopper.api.admin_delete_product(created[0]["id"])


@pytest.mark.feature("admin")
def test_admin_deletes_product_and_shoppers_no_longer_see_it(page, admin_shopper):
    """Deleting a product (with confirmation) marks it Deleted and removes it from the shop."""
    sku, name = unique_sku(), f"UI Test Doomed {unique_sku()}"
    body = {"sku": sku, "name": name, "category_slug": "gaming", "price_cents": 1234, "stock": 4}
    assert admin_shopper.api.admin_create_product(body).status_code == 201

    admin = AdminPage(page).open()
    admin.delete(sku)
    expect(admin.row(sku).get_by_test_id("admin-row-status")).to_have_text("Deleted")

    catalog = CatalogPage(page).open(q=name)
    expect(catalog.empty_results).to_be_visible()
