from playwright.sync_api import Locator, Page

from tests.ui.pages.base import BasePage, money_to_cents


class CartPage(BasePage):
    path = "/cart"

    def __init__(self, page: Page):
        super().__init__(page)
        self.root = self.tid("cart-page")
        self.items = self.tid("cart-item")
        self.empty = self.tid("cart-empty")
        self.error = self.tid("cart-error")
        self.coupon_input = self.tid("coupon-input")
        self.coupon_apply = self.tid("coupon-apply")
        self.coupon_applied = self.tid("coupon-applied")
        self.coupon_remove = self.tid("coupon-remove")
        self.coupon_error = self.tid("coupon-error")
        self.checkout_button = self.tid("checkout-button")

    def item(self, sku: str) -> Locator:
        return self.page.locator(f'[data-testid="cart-item"][data-sku="{sku}"]')

    def set_quantity(self, sku: str, quantity: int) -> None:
        row = self.item(sku)
        row.get_by_test_id("cart-item-quantity").fill(str(quantity))
        row.get_by_test_id("cart-item-update").click()

    def remove(self, sku: str) -> None:
        self.item(sku).get_by_test_id("cart-item-remove").click()

    def apply_coupon(self, code: str) -> None:
        self.coupon_input.fill(code)
        self.coupon_apply.click()

    def total(self, key: str) -> Locator:
        """key: subtotal | discount | tax | shipping | total"""
        return self.tid(f"cart-{key}")

    def totals_cents(self) -> dict[str, int]:
        keys = ("subtotal", "discount", "tax", "shipping", "total")
        return {f"{k}_cents": abs(money_to_cents(self.total(k).inner_text())) for k in keys}
