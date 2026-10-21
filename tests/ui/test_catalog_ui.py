import re

import pytest
from playwright.sync_api import expect

from tests.ui.pages import CatalogPage, ProductPage

pytestmark = [pytest.mark.ui, pytest.mark.feature("catalog")]


def test_catalog_shows_first_page_of_products(page):
    """The shop opens on page 1 with 12 product cards and a page indicator."""
    catalog = CatalogPage(page).open()
    expect(catalog.cards).to_have_count(12)
    expect(catalog.pagination_status).to_have_text(re.compile(r"^Page 1 of \d+$"))
    expect(catalog.prev_button).to_be_disabled()


def test_search_shows_only_matching_products(page):
    """Searching 'wireless' shows exactly the five wireless products."""
    catalog = CatalogPage(page).open()
    catalog.search("wireless")
    expect(catalog.results_count).to_have_text("5 products")
    assert all("wireless" in name.lower() for name in catalog.names())


@pytest.mark.bug("search_ignores_filters")
def test_category_filter_narrows_search_results(page):
    """Choosing the Gaming category after searching 'wireless' leaves only the game controller."""
    catalog = CatalogPage(page).open()
    catalog.search("wireless")
    catalog.choose_category("gaming")
    expect(catalog.cards).to_have_count(1)
    expect(catalog.card("GAM-001")).to_be_visible()


def test_search_with_no_matches_shows_empty_state(page):
    """A search with no matches shows a friendly empty message instead of a grid."""
    catalog = CatalogPage(page).open()
    catalog.search("zzz-no-such-gadget")
    expect(catalog.empty_results).to_be_visible()
    expect(catalog.cards).to_have_count(0)


@pytest.mark.bug("sort_desc_broken")
def test_sort_price_high_to_low(page):
    """'Price: high to low' puts the most expensive product first and keeps prices descending."""
    catalog = CatalogPage(page).open()
    catalog.sort_by("price_desc")
    prices = catalog.prices_cents()
    assert prices == sorted(prices, reverse=True), prices
    assert prices[0] == 24999


@pytest.mark.bug("pagination_off_by_one")
def test_next_page_shows_different_products(page):
    """Page 2 shows 12 products none of which were on page 1, and Previous returns to page 1."""
    catalog = CatalogPage(page).open()
    first_page = catalog.skus()
    catalog.next_page()
    expect(catalog.pagination_status).to_have_text(re.compile(r"^Page 2 of"))
    second_page = catalog.skus()
    assert len(second_page) == 12
    assert not set(first_page) & set(second_page), "a product appears on both pages"
    catalog.previous_page()
    assert catalog.skus() == first_page


def test_filters_are_kept_in_the_url(page):
    """Opening a URL with filters shows the filtered, sorted results directly."""
    catalog = CatalogPage(page).open(category="audio", sort="price_asc")
    expect(catalog.category_select).to_have_value("audio")
    expect(catalog.cards).to_have_count(8)
    prices = catalog.prices_cents()
    assert prices == sorted(prices)


def test_product_card_opens_matching_detail_page(page, catalog):
    """Clicking a product card opens its detail page with the same name and price."""
    listing = CatalogPage(page).open(q="earbuds")
    listing.open_product("AUD-001")
    detail = ProductPage(page)
    expect(detail.name).to_have_text(catalog["AUD-001"]["name"])
    assert detail.price_cents() == catalog["AUD-001"]["price_cents"]


def test_anonymous_visitor_is_asked_to_log_in_to_buy(page, catalog):
    """A logged-out visitor sees a login prompt instead of the add-to-cart button."""
    detail = ProductPage(page).open_by_id(catalog["AUD-001"]["id"])
    expect(detail.login_to_buy).to_be_visible()
    expect(detail.add_button).to_have_count(0)


@pytest.mark.feature("navigation")
def test_unknown_route_shows_not_found(page):
    """An unknown URL shows the not-found page with a way back to the shop."""
    page.goto("/this/does/not/exist")
    expect(page.get_by_test_id("not-found")).to_be_visible()
    page.get_by_test_id("not-found-home-link").click()
    expect(page.get_by_test_id("catalog-page")).to_be_visible()
