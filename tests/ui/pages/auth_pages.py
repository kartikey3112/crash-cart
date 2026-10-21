from playwright.sync_api import Page

from tests.ui.pages.base import BasePage


class LoginPage(BasePage):
    path = "/login"

    def __init__(self, page: Page):
        super().__init__(page)
        self.root = self.tid("login-page")
        self.email = self.tid("login-email")
        self.password = self.tid("login-password")
        self.submit = self.tid("login-submit")
        self.error = self.tid("login-error")

    def login(self, email: str, password: str) -> None:
        self.email.fill(email)
        self.password.fill(password)
        self.submit.click()


class RegisterPage(BasePage):
    path = "/register"

    def __init__(self, page: Page):
        super().__init__(page)
        self.full_name = self.tid("register-name")
        self.email = self.tid("register-email")
        self.password = self.tid("register-password")
        self.submit = self.tid("register-submit")
        self.error = self.tid("register-error")

    def register(self, full_name: str, email: str, password: str) -> None:
        self.full_name.fill(full_name)
        self.email.fill(email)
        self.password.fill(password)
        self.submit.click()
