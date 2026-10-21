"""Fixtures for the API suite."""

from collections.abc import Callable, Iterator

import pytest

from tests.api.client import StoreClient
from tests.api.data import PASSWORD, unique_email
from tests.config import RunConfig


@pytest.fixture(scope="session")
def make_client(run_config: RunConfig) -> Iterator[Callable[[], StoreClient]]:
    """Factory for anonymous clients. Every client sends the run's bug-switch headers."""
    clients: list[StoreClient] = []

    def _make() -> StoreClient:
        client = StoreClient(run_config.api_base_url, run_config.bug_headers)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.close()


@pytest.fixture(scope="session")
def anon(make_client) -> StoreClient:
    """A logged-out visitor."""
    return make_client()


@pytest.fixture
def new_customer(make_client) -> Callable[[], StoreClient]:
    """Factory: register a brand-new customer and return a client logged in as them."""

    def _create() -> StoreClient:
        client = make_client()
        email = unique_email()
        assert client.register(email, PASSWORD).status_code == 201
        assert client.login(email, PASSWORD).status_code == 200
        return client

    return _create


@pytest.fixture
def customer(new_customer) -> StoreClient:
    return new_customer()


@pytest.fixture(scope="session")
def admin(make_client, run_config: RunConfig) -> StoreClient:
    client = make_client()
    response = client.login(run_config.admin_email, run_config.admin_password)
    assert response.status_code == 200, f"admin login failed: {response.text}"
    return client


@pytest.fixture(scope="session")
def catalog(anon: StoreClient) -> dict[str, dict]:
    """Seeded products by SKU (ids are an implementation detail, SKUs are stable)."""
    products: dict[str, dict] = {}
    page, total_pages = 1, 1
    while page <= total_pages:  # walk every page: admin tests may add products meanwhile
        response = anon.products(page_size=50, page=page)
        assert response.status_code == 200, response.text
        body = response.json()
        products.update({p["sku"]: p for p in body["items"]})
        total_pages = body["total_pages"]
        page += 1
    return products


@pytest.fixture
def product_id(catalog) -> Callable[[str], int]:
    return lambda sku: catalog[sku]["id"]
