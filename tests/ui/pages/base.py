"""Base page object: the shared header plus helpers every page needs."""

import re

from playwright.sync_api import Locator, Page


def money_to_cents(text: str) -> int:
    """'$1,234.56' -> 123456 and '-$3.00' -> -300."""
    cleaned = text.strip().replace(",", "").replace("$", "")
    match = re.fullmatch(r"(-?)(\d+)\.(\d{2})", cleaned)
    if not match:
        raise ValueError(f"not a money amount: {text!r}")
    sign = -1 if match.group(1) else 1
    return sign * (int(match.group(2)) * 100 + int(match.group(3)))


class BasePage:
    path = "/"

    def __init__(self, page: Page):
        self.page = page
        # Header, present on every page.
        self.cart_count = page.get_by_test_id("cart-count")
        self.user_name = page.get_by_test_id("nav-user-name")
        self.logout_button = page.get_by_test_id("nav-logout")
        self.login_link = page.get_by_test_id("nav-login")
        self.register_link = page.get_by_test_id("nav-register")
        self.cart_link = page.get_by_test_id("nav-cart")
        self.orders_link = page.get_by_test_id("nav-orders")
        self.admin_link = page.get_by_test_id("nav-admin")

    def tid(self, test_id: str) -> Locator:
        return self.page.get_by_test_id(test_id)

    def open(self, path: str | None = None) -> "BasePage":
        self.page.goto(path or self.path)
        return self

    def logout(self) -> None:
        self.logout_button.click()
