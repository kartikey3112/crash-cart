from urllib.parse import urlencode

from playwright.sync_api import Locator, Page, expect

from tests.ui.pages.base import BasePage, money_to_cents


class CatalogPage(BasePage):
    path = "/"

    def __init__(self, page: Page):
        super().__init__(page)
        self.search_input = self.tid("search-input")
        self.search_button = self.tid("search-submit")
        self.min_price = self.tid("price-min")
        self.max_price = self.tid("price-max")
        self.category_select = self.tid("category-select")
        self.sort_select = self.tid("sort-select")
        self.cards = self.tid("product-card")
        self.results_count = self.tid("results-count")
        self.empty_results = self.tid("empty-results")
        self.pagination_status = self.tid("pagination-status")
        self.next_button = self.tid("pagination-next")
        self.prev_button = self.tid("pagination-prev")
        self.loading = self.tid("catalog-loading")

    # Every change triggers a GET /products. Waiting for that response, then for the
    # loading indicator to go, means assertions never read a stale page.
    def _after_products_load(self, action) -> None:
        # "/products?" matches the API call but not image files under /img/products/.
        with self.page.expect_response(lambda r: "/products?" in r.url):
            action()
        expect(self.loading).to_have_count(0)

    def open(self, **query) -> "CatalogPage":
        url = f"/?{urlencode(query)}" if query else "/"
        self._after_products_load(lambda: self.page.goto(url))
        return self

    def search(self, text: str) -> None:
        self.search_input.fill(text)
        self._after_products_load(self.search_button.click)

    def choose_category(self, slug: str) -> None:
        self._after_products_load(lambda: self.category_select.select_option(slug))

    def sort_by(self, value: str) -> None:
        self._after_products_load(lambda: self.sort_select.select_option(value))

    def next_page(self) -> None:
        self._after_products_load(self.next_button.click)

    def previous_page(self) -> None:
        self._after_products_load(self.prev_button.click)

    def card(self, sku: str) -> Locator:
        return self.page.locator(f'[data-testid="product-card"][data-sku="{sku}"]')

    def skus(self) -> list[str]:
        return [card.get_attribute("data-sku") for card in self.cards.all()]

    def names(self) -> list[str]:
        return self.tid("product-card-name").all_inner_texts()

    def prices_cents(self) -> list[int]:
        return [money_to_cents(t) for t in self.tid("product-card-price").all_inner_texts()]

    def open_product(self, sku: str) -> None:
        self.card(sku).get_by_test_id("product-card-link").click()
