import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.data import unique_sku
from tests.api.schemas import AdminProduct, Product

pytestmark = [pytest.mark.api, pytest.mark.feature("admin")]


def new_product_body(**changes) -> dict:
    body = {
        "sku": unique_sku(),
        "name": "API Test Gadget",
        "description": "Created by the API suite.",
        "category_slug": "gaming",
        "price_cents": 1234,
        "stock": 5,
    }
    return {**body, **changes}


@pytest.fixture
def temp_product(admin):
    """An admin-created product, soft-deleted again after the test."""
    product = expect_json(admin.admin_create_product(new_product_body()), 201, AdminProduct)
    yield product
    admin.admin_delete_product(product.id)


def test_admin_list_includes_soft_deleted(admin):
    """The admin product list includes inactive products, each matching the contract."""
    response = admin.admin_products()
    expect_status(response, 200)
    products = [AdminProduct.model_validate(p) for p in response.json()]
    assert any(not p.is_active for p in products)


def test_created_product_is_visible_to_shoppers(anon, temp_product):
    """A product created by an admin is immediately available in the public catalog."""
    shown = expect_json(anon.product(temp_product.id), 200, Product)
    assert (shown.sku, shown.price_cents) == (temp_product.sku, 1234)


@pytest.mark.parametrize(
    "changes",
    [
        {"price_cents": 0},
        {"price_cents": -100},
        {"price_cents": 1_000_001},
        {"stock": -1},
        {"sku": "lowercase-1"},
        {"sku": "AB-123"},
        {"name": ""},
    ],
    ids=[
        "price-zero",
        "price-negative",
        "price-too-high",
        "stock-negative",
        "sku-lowercase",
        "sku-short",
        "name-empty",
    ],
)
def test_create_rejects_invalid_fields(admin, changes):
    """Invalid price, stock, SKU format or empty name is a 422."""
    expect_status(admin.admin_create_product(new_product_body(**changes)), 422)


def test_create_with_unknown_category_is_422(admin):
    """A product must belong to an existing category."""
    response = admin.admin_create_product(new_product_body(category_slug="toys"))
    expect_error(response, 422, "unknown_category")


def test_duplicate_sku_is_409(admin):
    """SKUs are unique: reusing a seeded SKU is a 409."""
    expect_error(admin.admin_create_product(new_product_body(sku="AUD-001")), 409, "sku_taken")


def test_partial_update_changes_only_sent_fields(admin, temp_product):
    """PATCH with only a price leaves the name and stock unchanged."""
    updated = expect_json(
        admin.admin_update_product(temp_product.id, {"price_cents": 2000}), 200, AdminProduct
    )
    assert (updated.price_cents, updated.name, updated.stock) == (2000, temp_product.name, 5)


def test_soft_delete_hides_product_from_shoppers(admin, anon):
    """A deleted product disappears from the catalog but remains, inactive, for admins."""
    product = expect_json(admin.admin_create_product(new_product_body()), 201, AdminProduct)
    expect_status(admin.admin_delete_product(product.id), 204)
    expect_error(anon.product(product.id), 404, "product_not_found")
    still_there = [p for p in admin.admin_products().json() if p["id"] == product.id]
    assert still_there and still_there[0]["is_active"] is False


def test_deleting_twice_is_404(admin):
    """A product that is already deleted can't be deleted again."""
    product = expect_json(admin.admin_create_product(new_product_body()), 201, AdminProduct)
    expect_status(admin.admin_delete_product(product.id), 204)
    expect_error(admin.admin_delete_product(product.id), 404, "product_not_found")


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/admin/products"), ("POST", "/admin/products"), ("DELETE", "/admin/products/1")],
    ids=["list", "create", "delete"],
)
def test_customers_cannot_use_admin_endpoints(customer, method, path):
    """A logged-in customer gets 403 from every admin endpoint."""
    body = new_product_body() if method == "POST" else None
    expect_error(customer.request(method, path, json=body), 403, "forbidden")


def test_admin_endpoints_require_login(anon):
    """Anonymous requests to admin endpoints are 401."""
    expect_error(anon.admin_products(), 401, "not_authenticated")
