"""Fixtures for the UI suite (pytest-playwright).

- The browser talks to the frontend at UI_BASE_URL; bug switches (ENABLE_BUGS) are added to
  every browser request with Playwright's extra_http_headers.
- Setup work (creating users, filling carts, placing orders for other users) goes through
  the API WITHOUT bug headers: it's faster than clicking, and a bug under test can't break
  the setup itself.
- On failure, a screenshot is attached to the Allure report. Traces and screenshots are
  also saved under test-results/ by pytest-playwright (see pytest.ini).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

import allure
import pytest
from playwright.sync_api import Page, expect

from tests.api.client import StoreClient
from tests.api.data import PASSWORD, unique_email
from tests.config import RunConfig

# Free-tier backends can be slow; give UI assertions more headroom than the 5 s default.
expect.set_options(timeout=10_000)

TOKEN_STORAGE_KEY = "crashcart.token"  # must match store/frontend/src/api/client.ts


@dataclass
class Shopper:
    email: str
    api: StoreClient  # logged-in API client for setup and cross-checks


@pytest.fixture(scope="session")
def base_url(run_config: RunConfig) -> str:
    # Overrides pytest-base-url so page.goto("/cart") resolves against the frontend.
    return run_config.ui_base_url


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict, run_config: RunConfig) -> dict:
    args = {**browser_context_args, "viewport": {"width": 1280, "height": 900}}
    if run_config.bug_headers:
        args["extra_http_headers"] = run_config.bug_headers
    return args


@pytest.fixture
def setup_api(run_config: RunConfig) -> Iterator[Callable[[], StoreClient]]:
    """Factory for clean API clients (never carry bug headers)."""
    clients: list[StoreClient] = []

    def _make() -> StoreClient:
        client = StoreClient(run_config.api_base_url)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.close()


@pytest.fixture
def make_shopper(setup_api) -> Callable[[], Shopper]:
    """Factory: register a new customer through the API."""

    def _make() -> Shopper:
        client, email = setup_api(), unique_email()
        assert client.register(email, PASSWORD, "UI Tester").status_code == 201
        assert client.login(email, PASSWORD).status_code == 200
        return Shopper(email=email, api=client)

    return _make


def sign_in_browser(page: Page, token: str) -> None:
    """Put the token where the app keeps it, so the browser starts already logged in."""
    page.goto("/")
    page.evaluate(f"t => localStorage.setItem('{TOKEN_STORAGE_KEY}', t)", token)


@pytest.fixture
def shopper(page: Page, make_shopper) -> Shopper:
    """A new customer, already logged in in the browser."""
    user = make_shopper()
    sign_in_browser(page, user.api.token)
    return user


@pytest.fixture
def admin_shopper(page: Page, setup_api, run_config: RunConfig) -> Shopper:
    client = setup_api()
    assert client.login(run_config.admin_email, run_config.admin_password).status_code == 200
    sign_in_browser(page, client.token)
    return Shopper(email=run_config.admin_email, api=client)


@pytest.fixture(scope="session")
def catalog(run_config: RunConfig) -> dict[str, dict]:
    """Seeded products by SKU, read once through the API."""
    client = StoreClient(run_config.api_base_url)
    products: dict[str, dict] = {}
    try:
        page, total_pages = 1, 1
        while page <= total_pages:
            body = client.products(page_size=50, page=page).json()
            products.update({p["sku"]: p for p in body["items"]})
            total_pages, page = body["total_pages"], page + 1
        return products
    finally:
        client.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    outcome = yield
    report = outcome.get_result()
    page = item.funcargs.get("page") if hasattr(item, "funcargs") else None
    if report.when == "call" and report.failed and page is not None:
        try:
            allure.attach(
                page.screenshot(full_page=True),
                name="screenshot-on-failure",
                attachment_type=allure.attachment_type.PNG,
            )
            allure.attach(
                page.url, name="url-on-failure", attachment_type=allure.attachment_type.TEXT
            )
        except Exception:  # noqa: BLE001 - a broken page must not hide the real failure
            pass
