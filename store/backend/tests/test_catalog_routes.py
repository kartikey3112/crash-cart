import time

import pytest

from tests.helpers import UNIT_TEST_TOKEN, bug_headers

pytestmark = [pytest.mark.unit, pytest.mark.feature("catalog")]


@pytest.mark.feature("health")
def test_health_reports_ok(client):
    """/health answers 200 with status and database both ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "ok"


def test_six_categories_seeded(client):
    """The seed creates six categories."""
    assert len(client.get("/categories").json()) == 6


def test_default_listing_has_four_pages(client):
    """48 active products at 12 per page gives exactly 4 pages."""
    body = client.get("/products").json()
    assert (body["total"], body["total_pages"], len(body["items"])) == (48, 4, 12)


def test_inactive_product_is_hidden(client, admin):
    """The soft-deleted seed product appears in neither search nor detail."""
    inactive = next(
        p for p in client.get("/admin/products", headers=admin).json() if not p["is_active"]
    )
    assert client.get("/products", params={"q": "Cassette"}).json()["total"] == 0
    assert client.get(f"/products/{inactive['id']}").status_code == 404


def test_unknown_product_returns_404(client):
    """A product id that doesn't exist returns 404 with an error code."""
    response = client.get("/products/99999")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "product_not_found"


def test_search_with_category_filter(client):
    """Searching "wireless" within gaming returns only the gaming controller."""
    body = client.get("/products", params={"q": "wireless", "category": "gaming"}).json()
    assert [p["sku"] for p in body["items"]] == ["GAM-001"]


@pytest.mark.bug("search_ignores_filters")
def test_search_ignores_filters_bug(client):
    """With the bug on, the category filter is dropped and all 5 wireless products return."""
    params = {"q": "wireless", "category": "gaming"}
    body = client.get(
        "/products", params=params, headers=bug_headers("search_ignores_filters")
    ).json()
    assert body["total"] == 5


def test_price_range_filter(client):
    """min/max price filters are inclusive at both ends."""
    params = {"min_price_cents": 799, "max_price_cents": 999, "page_size": 50}
    prices = sorted(
        p["price_cents"] for p in client.get("/products", params=params).json()["items"]
    )
    assert prices == [799, 899, 899, 999]


def test_min_price_above_max_is_rejected(client):
    """An impossible price range is a 422, not an empty result."""
    response = client.get("/products", params={"min_price_cents": 500, "max_price_cents": 100})
    assert response.status_code == 422


def test_sort_price_desc(client):
    """sort=price_desc puts the most expensive product first."""
    first = client.get("/products", params={"sort": "price_desc"}).json()["items"][0]
    assert first["price_cents"] == 24999


@pytest.mark.bug("sort_desc_broken")
def test_sort_desc_broken_bug(client):
    """With the bug on, price_desc actually returns the cheapest product first."""
    headers = bug_headers("sort_desc_broken")
    first = client.get("/products", params={"sort": "price_desc"}, headers=headers).json()["items"][
        0
    ]
    assert first["price_cents"] == 799


def test_pages_do_not_overlap(client):
    """Consecutive pages share no products."""
    page1 = {p["id"] for p in client.get("/products", params={"page": 1}).json()["items"]}
    page2 = {p["id"] for p in client.get("/products", params={"page": 2}).json()["items"]}
    assert page1.isdisjoint(page2)


@pytest.mark.bug("pagination_off_by_one")
def test_pagination_off_by_one_bug(client):
    """With the bug on, page 2 starts with the last product of page 1."""
    headers = bug_headers("pagination_off_by_one")
    page1 = client.get("/products", params={"page": 1}, headers=headers).json()["items"]
    page2 = client.get("/products", params={"page": 2}, headers=headers).json()["items"]
    assert page2[0]["id"] == page1[-1]["id"]


@pytest.mark.parametrize(("page_size", "status"), [(0, 422), (1, 200), (50, 200), (51, 422)])
def test_page_size_boundaries(client, page_size, status):
    """page_size accepts 1-50 and rejects values just outside that range."""
    assert client.get("/products", params={"page_size": page_size}).status_code == status


def test_page_past_end_is_empty(client):
    """Asking for a page beyond the last one returns no items rather than an error."""
    body = client.get("/products", params={"page": 99}).json()
    assert body["items"] == [] and body["total"] == 48


@pytest.mark.bug("slow_products")
def test_slow_products_bug(client):
    """With the bug on, GET /products takes at least the configured delay (300 ms here)."""
    start = time.perf_counter()
    client.get("/products", headers=bug_headers("slow_products"))
    assert time.perf_counter() - start >= 0.3


@pytest.mark.feature("bug-switches")
def test_active_bugs_are_echoed(client):
    """The response confirms which bugs were really enabled."""
    response = client.get("/products", headers=bug_headers("sort_desc_broken", "slow_products"))
    assert response.headers["X-Bug-Switches-Active"] == "slow_products,sort_desc_broken"


@pytest.mark.feature("bug-switches")
def test_bug_header_without_token_does_nothing(client):
    """Without the token, a visitor's bug header is ignored and no bug is reported active."""
    response = client.get(
        "/products", params={"sort": "price_desc"}, headers={"X-Bug-Switches": "sort_desc_broken"}
    )
    assert "X-Bug-Switches-Active" not in response.headers
    assert response.json()["items"][0]["price_cents"] == 24999


@pytest.mark.feature("bug-switches")
def test_unknown_bug_with_token_is_400(client):
    """A misspelled switch with a valid token is rejected with 400."""
    headers = {"X-Bug-Switches": "sort_desc_brokn", "X-Test-Token": UNIT_TEST_TOKEN}
    response = client.get("/products", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unknown_bug"
