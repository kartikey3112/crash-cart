from playwright.sync_api import Page

from tests.ui.pages.base import BasePage, money_to_cents


class OrdersPage(BasePage):
    path = "/orders"

    def __init__(self, page: Page):
        super().__init__(page)
        self.root = self.tid("orders-page")
        self.rows = self.tid("order-row")
        self.empty = self.tid("orders-empty")

    def order_ids(self) -> list[int]:
        return [int(row.get_attribute("data-order-id")) for row in self.rows.all()]


class OrderDetailPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.root = self.tid("order-detail")
        self.confirmation = self.tid("order-confirmation")
        self.order_id = self.tid("order-id")
        self.items = self.tid("order-item")
        self.error = self.tid("order-error")
        self.total = self.tid("order-total")

    def open_by_id(self, order_id: int) -> "OrderDetailPage":
        self.page.goto(f"/orders/{order_id}")
        return self

    def id_from_url(self) -> int:
        return int(self.page.url.split("/orders/")[1].split("?")[0])

    def total_cents(self) -> int:
        return money_to_cents(self.total.inner_text())
