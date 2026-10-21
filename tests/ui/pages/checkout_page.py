from playwright.sync_api import Page

from tests.ui.pages.base import BasePage, money_to_cents


class CheckoutPage(BasePage):
    path = "/checkout"

    def __init__(self, page: Page):
        super().__init__(page)
        self.root = self.tid("checkout-page")
        self.demo_banner = self.tid("demo-payment-banner")
        self.place_order_button = self.tid("place-order")
        self.error = self.tid("checkout-error")
        self.total = self.tid("checkout-total")
        self.form = self.tid("checkout-form")

    def fill_shipping(self, shipping: dict) -> None:
        self.tid("shipping-name").fill(shipping["full_name"])
        self.tid("shipping-address").fill(shipping["address_line1"])
        self.tid("shipping-city").fill(shipping["city"])
        self.tid("shipping-postal").fill(shipping["postal_code"])
        self.tid("shipping-country").fill(shipping["country"])

    def fill_card(self, card: dict) -> None:
        self.tid("card-number").fill(card["number"])
        self.tid("card-expiry").fill(card["expiry"])
        self.tid("card-cvv").fill(card["cvv"])
        self.tid("card-name").fill(card["name_on_card"])

    def total_cents(self) -> int:
        return money_to_cents(self.total.inner_text())

    def place_order(self) -> None:
        self.place_order_button.click()

    def submit_twice_quickly(self) -> None:
        """Fire two submit events in the same tick, like a fast double click that beats the
        button's disabled state. The server must still create only one order."""
        self.form.evaluate("form => { form.requestSubmit(); form.requestSubmit(); }")
