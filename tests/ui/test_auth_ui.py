import pytest
from playwright.sync_api import expect

from tests.api.data import PASSWORD, unique_email
from tests.ui.pages import LoginPage, OrdersPage, RegisterPage

pytestmark = [pytest.mark.ui, pytest.mark.feature("auth")]


def test_register_logs_the_new_user_in(page):
    """Signing up logs the user straight in: their name and an empty cart badge appear."""
    register = RegisterPage(page).open()
    register.register("Priya Tester", unique_email(), PASSWORD)
    expect(register.user_name).to_have_text("Priya Tester")
    expect(register.cart_count).to_have_text("0")


def test_register_with_short_password_shows_error(page):
    """A password shorter than 8 characters is refused with a visible error."""
    register = RegisterPage(page).open()
    register.register("Short Pass", unique_email(), "1234567")
    expect(register.error).to_be_visible()
    expect(register.user_name).to_have_count(0)


def test_login_with_wrong_password_shows_error(page, make_shopper):
    """A wrong password shows 'Invalid email or password' and the user stays logged out."""
    user = make_shopper()
    login = LoginPage(page).open()
    login.login(user.email, "definitely-wrong")
    expect(login.error).to_have_text("Invalid email or password")
    expect(login.login_link).to_be_visible()


def test_logout_returns_to_logged_out_header(page, make_shopper):
    """Logging out removes the user's name and shows the login link again."""
    user = make_shopper()
    login = LoginPage(page).open()
    login.login(user.email, PASSWORD)
    expect(login.user_name).to_have_text("UI Tester")
    login.logout()
    expect(login.login_link).to_be_visible()
    expect(login.user_name).to_have_count(0)


def test_protected_page_redirects_to_login_then_back(page, make_shopper):
    """Opening /orders while logged out goes to login, and logging in returns to /orders."""
    user = make_shopper()
    page.goto("/orders")
    login = LoginPage(page)
    expect(login.root).to_be_visible()
    login.login(user.email, PASSWORD)
    expect(OrdersPage(page).root).to_be_visible()
    assert page.url.endswith("/orders")
