"""Fixtures for backend unit tests: a fresh in-memory store per test, driven by TestClient."""

import itertools
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.helpers import ADMIN_EMAIL, ADMIN_PASSWORD, UNIT_TEST_TOKEN, login

_user_counter = itertools.count(1)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # ignore any developer .env so tests are reproducible
        database_url="sqlite://",  # in-memory: every test starts from a clean seed
        bcrypt_rounds=4,  # minimum cost keeps hashing fast in tests
        test_token=UNIT_TEST_TOKEN,
        admin_email=ADMIN_EMAIL,
        admin_password=ADMIN_PASSWORD,
        slow_bug_delay_ms=300,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    # The context manager runs the app lifespan, which seeds the database.
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def new_customer(client: TestClient):
    """Factory: register a unique customer and return their auth headers."""

    def _create() -> dict[str, str]:
        email = f"customer{next(_user_counter)}@unit.test"
        response = client.post(
            "/auth/register",
            json={"email": email, "password": "password123", "full_name": "Unit Customer"},
        )
        assert response.status_code == 201, response.text
        return login(client, email, "password123")

    return _create


@pytest.fixture
def customer(new_customer) -> dict[str, str]:
    return new_customer()


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
