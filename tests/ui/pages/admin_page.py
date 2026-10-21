from playwright.sync_api import Locator, Page

from tests.ui.pages.base import BasePage


class AdminPage(BasePage):
    path = "/admin"

    def __init__(self, page: Page):
        super().__init__(page)
        self.root = self.tid("admin-page")
        self.forbidden = self.tid("admin-forbidden")
        self.success = self.tid("admin-form-success")
        self.error = self.tid("admin-form-error")
        self.table = self.tid("admin-product-table")

    def row(self, sku: str) -> Locator:
        return self.page.locator(f'[data-testid="admin-product-row"][data-sku="{sku}"]')

    def create_product(
        self, sku: str, name: str, category: str, price: str, stock: int, description: str = ""
    ) -> None:
        self.tid("admin-sku").fill(sku)
        self.tid("admin-name").fill(name)
        self.tid("admin-category").select_option(category)
        self.tid("admin-price").fill(price)
        self.tid("admin-stock").fill(str(stock))
        self.tid("admin-description").fill(description)
        self.tid("admin-submit").click()

    def delete(self, sku: str) -> None:
        row = self.row(sku)
        row.get_by_test_id("admin-delete").click()
        row.get_by_test_id("admin-delete-confirm").click()
