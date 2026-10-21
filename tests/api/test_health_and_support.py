import httpx
import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.schemas import Health
from tests.config import KNOWN_BUGS

pytestmark = pytest.mark.api


@pytest.mark.feature("health")
def test_health_reports_ok(anon):
    """GET /health returns 200 and matches the health contract."""
    expect_json(anon.health(), 200, Health)


@pytest.mark.feature("api-contract")
def test_openapi_spec_lists_every_endpoint(anon):
    """The live OpenAPI spec documents every endpoint the store promises."""
    response = anon.request("GET", "/openapi.json")
    expect_status(response, 200)
    paths = set(response.json()["paths"])
    expected = {
        "/health", "/auth/register", "/auth/login", "/auth/me", "/categories", "/products",
        "/products/{product_id}", "/cart", "/cart/items", "/cart/items/{product_id}",
        "/cart/coupon", "/checkout", "/orders", "/orders/{order_id}", "/admin/products",
        "/admin/products/{product_id}", "/test/reset", "/test/bugs",
    }  # fmt: skip
    assert expected <= paths, f"missing from spec: {sorted(expected - paths)}"


@pytest.mark.feature("test-support")
@pytest.mark.parametrize("token", [None, "wrong-token"], ids=["no-token", "wrong-token"])
def test_reset_requires_valid_token(run_config, token):
    """POST /test/reset is refused without the correct X-Test-Token."""
    headers = {"X-Test-Token": token} if token else {}
    response = httpx.post(f"{run_config.api_base_url}/test/reset", headers=headers, timeout=30)
    expect_error(response, 401, "invalid_test_token")


@pytest.mark.feature("test-support")
def test_bug_registry_matches_test_suite(run_config):
    """The server's bug switches are exactly the ones this suite knows how to catch."""
    response = httpx.get(
        f"{run_config.api_base_url}/test/bugs",
        headers={"X-Test-Token": run_config.test_token},
        timeout=30,
    )
    expect_status(response, 200)
    assert {bug["name"] for bug in response.json()} == set(KNOWN_BUGS)


@pytest.mark.feature("bug-switches")
def test_bug_header_without_token_is_ignored(run_config):
    """A visitor sending a bug header without the token gets the normal, correct store."""
    response = httpx.get(
        f"{run_config.api_base_url}/products",
        params={"sort": "price_desc"},
        headers={"X-Bug-Switches": "sort_desc_broken"},
        timeout=30,
    )
    expect_status(response, 200)
    assert "X-Bug-Switches-Active" not in response.headers
    prices = [p["price_cents"] for p in response.json()["items"]]
    assert prices == sorted(prices, reverse=True)


@pytest.mark.feature("bug-switches")
def test_unknown_bug_switch_is_rejected(run_config):
    """A misspelled switch with a valid token is a 400, so a typo can't hide a missing bug."""
    response = httpx.get(
        f"{run_config.api_base_url}/products",
        headers={"X-Bug-Switches": "not_a_real_bug", "X-Test-Token": run_config.test_token},
        timeout=30,
    )
    expect_error(response, 400, "unknown_bug")
