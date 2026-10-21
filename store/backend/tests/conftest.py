"""Fixtures for backend unit tests: a fresh in-memory store per test, driven by TestClient.

Like the system tests, every unit test needs a feature marker and a docstring; the results
dashboard lists them in their own "unit tests" section (--catalog-out writes that list).
"""

import itertools
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.helpers import ADMIN_EMAIL, ADMIN_PASSWORD, UNIT_TEST_TOKEN, login

_user_counter = itertools.count(1)
# Unit-test ids are reported relative to the repo root so they never clash with system tests.
ID_PREFIX = "store/backend/"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--catalog-out", default=None, help="Write a JSON catalog of unit tests.")


def _test_info(item: pytest.Item) -> dict:
    feature = item.get_closest_marker("feature")
    return {
        "id": ID_PREFIX + item.nodeid,
        "name": item.name,
        "file": ID_PREFIX + item.location[0].replace("\\", "/"),
        "layer": "unit",
        "feature": feature.args[0] if feature and feature.args else None,
        "bugs": [m.args[0] for m in item.iter_markers("bug") if m.args],
        "docstring": (item.function.__doc__ or "").strip(),
    }


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    infos = [_test_info(item) for item in items]
    problems = [
        f"{info['id']}: missing {what}"
        for info in infos
        for what, ok in (("feature marker", info["feature"]), ("docstring", info["docstring"]))
        if not ok
    ]
    if problems:
        raise pytest.UsageError("Unit test metadata problems:\n  " + "\n  ".join(problems))
    if out := config.getoption("--catalog-out"):
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(infos, indent=2), encoding="utf-8")


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
