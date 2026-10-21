"""Short load tests on key endpoints. Each fails if p95 latency or the error rate exceeds
its budget (see tests/perf/conftest.py for the environment variables)."""

import os

import pytest

from tests.perf.jmeter_runner import PerfStats

pytestmark = pytest.mark.perf


def check_budget(stats: PerfStats, budget_ms: int) -> None:
    max_error_rate = float(os.getenv("PERF_MAX_ERROR_RATE", "0.01"))
    detail = (
        f"p50={stats.p50_ms}ms p95={stats.p95_ms}ms p99={stats.p99_ms}ms max={stats.max_ms}ms "
        f"samples={stats.samples} errors={stats.errors} rps={stats.throughput_rps}"
    )
    assert stats.error_rate <= max_error_rate, (
        f"error rate {stats.error_rate:.2%} too high; {detail}"
    )
    assert stats.p95_ms <= budget_ms, f"p95 {stats.p95_ms}ms over budget {budget_ms}ms; {detail}"


@pytest.mark.feature("catalog")
@pytest.mark.bug("slow_products")
def test_products_list_p95(run_scenario):
    """Under light load, the first catalog page keeps p95 latency within budget."""
    check_budget(*run_scenario("products_list", "/products?page=1&page_size=12"))


@pytest.mark.feature("catalog")
@pytest.mark.bug("slow_products")
def test_product_search_p95(run_scenario):
    """Under light load, a filtered product search keeps p95 latency within budget."""
    path = "/products?q=wireless&max_price_cents=10000&sort=price_asc"
    check_budget(*run_scenario("product_search", path))


@pytest.mark.feature("catalog")
def test_product_detail_p95(run_scenario, perf_customer):
    """Under light load, a product detail page keeps p95 latency within budget."""
    product_id = perf_customer.products(q="Pulse Wireless").json()["items"][0]["id"]
    check_budget(*run_scenario("product_detail", f"/products/{product_id}"))


@pytest.mark.feature("cart")
def test_cart_read_p95(run_scenario, perf_customer):
    """Under light load, reading a logged-in customer's cart keeps p95 latency within budget."""
    check_budget(*run_scenario("cart_read", "/cart", token=perf_customer.token))
