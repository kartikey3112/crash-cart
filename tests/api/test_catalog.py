import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.schemas import Category, Product, ProductPage

pytestmark = [pytest.mark.api, pytest.mark.feature("catalog")]

# Upper bound for GET /products on a warm server. The slow_products bug adds ~2 s.
PRODUCTS_SLA_SECONDS = 1.5


def all_pages(client, **params) -> list[dict]:
    """Follow pagination to the end and return every item in order."""
    items, page = [], 1
    while True:
        body = expect_json(client.products(page=page, **params), 200, ProductPage)
        items += [p.model_dump() for p in body.items]
        if page >= body.total_pages:
            return items
        page += 1


def test_categories_contract(anon):
    """GET /categories returns the six seeded categories, each matching the contract."""
    response = anon.categories()
    expect_status(response, 200)
    categories = [Category.model_validate(c) for c in response.json()]
    assert {c.slug for c in categories} == {
        "audio", "wearables", "smart-home", "computer-accessories", "phone-accessories", "gaming",
    }  # fmt: skip


def test_product_listing_contract_and_defaults(anon):
    """The default listing is page 1 with 12 items and consistent page maths."""
    page = expect_json(anon.products(), 200, ProductPage)
    assert (page.page, page.page_size, len(page.items)) == (1, 12, 12)
    assert page.total_pages == -(-page.total // page.page_size)  # ceiling division


def test_category_filter_returns_only_that_category(anon):
    """Filtering by category returns exactly the 8 seeded audio products and nothing else."""
    items = all_pages(anon, category="audio")
    assert len(items) == 8
    assert {p["category"]["slug"] for p in items} == {"audio"}


def test_search_matches_name_case_insensitively(anon):
    """Searching 'WIRELESS' finds every product with 'wireless' in its name or description."""
    items = all_pages(anon, q="WIRELESS")
    assert len(items) == 5
    assert all("wireless" in (p["name"] + p["description"]).lower() for p in items)


@pytest.mark.bug("search_ignores_filters")
def test_search_respects_category_filter(anon):
    """Search combined with a category returns only matching products in that category."""
    items = all_pages(anon, q="wireless", category="gaming")
    assert [p["sku"] for p in items] == ["GAM-001"]


@pytest.mark.bug("search_ignores_filters")
def test_search_respects_price_filter(anon):
    """Search combined with a max price never returns products above that price."""
    items = all_pages(anon, q="wireless", max_price_cents=2500)
    assert items, "expected at least one cheap wireless product"
    assert all(p["price_cents"] <= 2500 for p in items)


def test_price_range_is_inclusive(anon):
    """min/max price filters include products priced exactly at either bound."""
    prices = sorted(
        p["price_cents"] for p in all_pages(anon, min_price_cents=799, max_price_cents=999)
    )
    assert prices == [799, 899, 899, 999]


def test_inverted_price_range_is_rejected(anon):
    """A minimum price above the maximum is a 422, not a silently empty result."""
    expect_error(
        anon.products(min_price_cents=1000, max_price_cents=10), 422, "invalid_price_range"
    )


def test_sort_price_ascending(anon):
    """sort=price_asc returns every product in non-decreasing price order."""
    prices = [p["price_cents"] for p in all_pages(anon, sort="price_asc")]
    assert prices == sorted(prices)


@pytest.mark.bug("sort_desc_broken")
def test_sort_price_descending(anon):
    """sort=price_desc returns every product in non-increasing price order."""
    prices = [p["price_cents"] for p in all_pages(anon, sort="price_desc")]
    assert prices == sorted(prices, reverse=True)


def test_sort_by_name(anon):
    """The default sort is alphabetical by name."""
    names = [p["name"] for p in all_pages(anon, category="gaming")]
    assert names == sorted(names)


@pytest.mark.parametrize("sort", ["cheapest", "PRICE_ASC", ""])
def test_invalid_sort_is_422(anon, sort):
    """Unknown sort values are rejected rather than ignored."""
    expect_status(anon.products(sort=sort), 422)


@pytest.mark.bug("pagination_off_by_one")
def test_pages_cover_catalog_without_overlap(anon, catalog):
    """Walking all pages yields every product exactly once."""
    walked = all_pages(anon, page_size=12)
    skus = [p["sku"] for p in walked]
    duplicates = sorted({s for s in skus if skus.count(s) > 1})
    assert not duplicates, f"products on more than one page: {duplicates}"
    # Compare with seeded SKUs, not a total: parallel admin tests may add products.
    missing = sorted(set(catalog) - set(skus))
    assert not missing, f"products never shown: {missing}"


@pytest.mark.parametrize(
    ("page_size", "status"), [(0, 422), (1, 200), (50, 200), (51, 422)], ids=lambda v: str(v)
)
def test_page_size_boundaries(anon, page_size, status):
    """page_size accepts 1 to 50 and rejects the values just outside."""
    expect_status(anon.products(page_size=page_size), status)


@pytest.mark.parametrize("page", [0, -1])
def test_page_must_be_positive(anon, page):
    """page numbers start at 1."""
    expect_status(anon.products(page=page), 422)


def test_page_past_the_end_is_empty(anon):
    """A page beyond the last returns 200 with no items (not an error)."""
    page = expect_json(anon.products(page=999), 200, ProductPage)
    assert page.items == [] and page.total > 0


def test_product_detail_matches_listing(anon, catalog):
    """GET /products/{id} returns the same product the listing shows."""
    listed = catalog["AUD-001"]
    detail = expect_json(anon.product(listed["id"]), 200, Product)
    # Stock is left out on purpose: other tests may buy this product in parallel.
    assert (detail.sku, detail.name, detail.price_cents, detail.category.slug) == (
        listed["sku"],
        listed["name"],
        listed["price_cents"],
        listed["category"]["slug"],
    )


def test_unknown_product_is_404(anon):
    """A product id that doesn't exist is a 404 with an error code."""
    expect_error(anon.product(999999), 404, "product_not_found")


def test_soft_deleted_product_is_hidden(anon, admin):
    """The seeded discontinued product is invisible to shoppers but still known to admins."""
    hidden = [p for p in admin.admin_products().json() if p["sku"] == "AUD-009"][0]
    assert hidden["is_active"] is False
    expect_error(anon.product(hidden["id"]), 404, "product_not_found")
    assert all_pages(anon, q="Cassette") == []


@pytest.mark.bug("slow_products")
def test_product_listing_responds_quickly(anon):
    """GET /products answers within the latency budget on a warm server."""
    anon.products()  # warm-up request
    response = anon.products()
    expect_status(response, 200)
    elapsed = response.elapsed.total_seconds()
    assert elapsed < PRODUCTS_SLA_SECONDS, f"took {elapsed:.2f}s (budget {PRODUCTS_SLA_SECONDS}s)"
