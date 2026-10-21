"""Fixtures for the perf suite.

Load profile and thresholds come from environment variables, so CI and local runs can
use different budgets without code changes:
  PERF_USERS (10), PERF_RAMPUP_S (5), PERF_DURATION_S (60), PERF_THINK_MS (100)
  PERF_P95_MS_<SCENARIO> (800), e.g. PERF_P95_MS_PRODUCTS_LIST=600
  PERF_MAX_ERROR_RATE (0.01), PERF_RESULTS_DIR (perf-results)
"""

import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path

import allure
import httpx
import pytest

from tests.api.client import StoreClient
from tests.api.data import GENERAL_ITEM, PASSWORD, unique_email
from tests.config import RunConfig
from tests.perf.jmeter_runner import LoadProfile, PerfStats, run_jmeter

DEFAULT_P95_MS = 800


def p95_budget_ms(scenario: str) -> int:
    return int(os.getenv(f"PERF_P95_MS_{scenario.upper()}", DEFAULT_P95_MS))


@pytest.fixture(scope="session")
def load_profile() -> LoadProfile:
    return LoadProfile(
        threads=int(os.getenv("PERF_USERS", "10")),
        rampup_s=int(os.getenv("PERF_RAMPUP_S", "5")),
        duration_s=int(os.getenv("PERF_DURATION_S", "60")),
        think_ms=int(os.getenv("PERF_THINK_MS", "100")),
    )


@pytest.fixture(scope="session")
def results_dir() -> Path:
    return Path(os.getenv("PERF_RESULTS_DIR", "perf-results"))


@pytest.fixture(scope="session")
def perf_customer(run_config: RunConfig) -> Iterator[StoreClient]:
    """A customer with one item in their cart, for authenticated scenarios (setup: no bugs)."""
    client = StoreClient(run_config.api_base_url)
    email = unique_email()
    client.register(email, PASSWORD, "Perf Tester")
    assert client.login(email, PASSWORD).status_code == 200
    general = client.products(q="Braided").json()["items"][0]
    assert general["sku"] == GENERAL_ITEM
    client.add_to_cart(general["id"], 1)
    yield client
    client.close()


@pytest.fixture
def run_scenario(
    run_config: RunConfig, load_profile: LoadProfile, results_dir: Path
) -> Callable[..., tuple[PerfStats, int]]:
    """Run one load scenario; returns (stats, p95 budget) and saves a JSON summary."""

    def _run(scenario: str, path: str, token: str = "") -> tuple[PerfStats, int]:
        # Warm-up outside the measurement: wakes the instance and fills caches.
        for _ in range(5):
            httpx.get(
                f"{run_config.api_base_url}{path}",
                headers={"Authorization": f"Bearer {token}"} if token else {},
                timeout=30,
            )
        stats = run_jmeter(
            base_url=run_config.api_base_url,
            path=path,
            label=scenario,
            profile=load_profile,
            out_dir=results_dir,
            token=token,
            bug_switches=",".join(run_config.enabled_bugs),
            test_token=run_config.test_token if run_config.enabled_bugs else "",
        )
        budget = p95_budget_ms(scenario)
        summary = {
            "scenario": scenario,
            "path": path,
            "profile": load_profile.__dict__,
            "p95_budget_ms": budget,
            "max_error_rate": float(os.getenv("PERF_MAX_ERROR_RATE", "0.01")),
            "enabled_bugs": list(run_config.enabled_bugs),
            "stats": stats.to_dict(),
            "passed": stats.p95_ms <= budget,
        }
        text = json.dumps(summary, indent=2)
        (results_dir / f"{scenario}.json").write_text(text, encoding="utf-8")
        allure.attach(text, name=f"{scenario} stats", attachment_type=allure.attachment_type.JSON)
        return stats, budget

    return _run
