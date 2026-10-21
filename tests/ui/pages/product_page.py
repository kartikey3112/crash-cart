from playwright.sync_api import Page

from tests.ui.pages.base import BasePage, money_to_cents


class ProductPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.detail = self.tid("product-detail")
        self.name = self.tid("product-name")
        self.price = self.tid("product-price")
        self.stock = self.tid("product-stock")
        self.quantity = self.tid("quantity-input")
        self.add_button = self.tid("add-to-cart")
        self.added_message = self.tid("add-to-cart-success")
        self.error = self.tid("add-to-cart-error")
        self.login_to_buy = self.tid("login-to-buy")

    def open_by_id(self, product_id: int) -> "ProductPage":
        self.page.goto(f"/products/{product_id}")
        return self

    def price_cents(self) -> int:
        return money_to_cents(self.price.inner_text())

    def add_to_cart(self, quantity: int = 1) -> None:
        self.quantity.fill(str(quantity))
        self.add_button.click()
