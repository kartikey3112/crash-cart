"""Shared setup for all system-test layers (api, ui, perf).

Session start (once, on the xdist controller only):
  1. wait for the backend's /health (free-tier hosts sleep and take ~1 min to wake)
  2. reset the store to its seed state

Collection: every test must declare exactly one layer marker, a feature marker and a
one-line docstring. The dashboard's test catalog is generated from these, so a test
missing any of them stops the run.
"""

import json
import time
from pathlib import Path

import allure
import httpx
import pytest

from tests.config import KNOWN_BUGS, RunConfig, load_config

LAYERS = ("api", "ui", "perf", "demo")  # demo: tests/noisefloor_demo, off by default


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--catalog-out",
        default=None,
        help="Write a JSON catalog of the collected tests (id, layer, feature, bugs, docstring).",
    )


def pytest_report_header(config: pytest.Config) -> list[str]:
    cfg = load_config()
    return [
        f"CrashCart API: {cfg.api_base_url}   UI: {cfg.ui_base_url}",
        f"Bug switches enabled for this run: {', '.join(cfg.enabled_bugs) or 'none'}",
    ]


def _is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def _write(config: pytest.Config, line: str) -> None:
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter:
        reporter.write_line(line)


def wait_for_health(cfg: RunConfig) -> float:
    """Poll /health until it answers ok. Returns seconds waited; raises TimeoutError."""
    start = time.monotonic()
    last_error = "no response yet"
    while time.monotonic() - start < cfg.wake_timeout_s:
        try:
            response = httpx.get(f"{cfg.api_base_url}/health", timeout=10)
            if response.status_code == 200 and response.json().get("status") == "ok":
                return time.monotonic() - start
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(3)
    raise TimeoutError(
        f"Backend at {cfg.api_base_url} was not healthy within {cfg.wake_timeout_s}s. "
        f"Last error: {last_error}"
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    config = session.config
    if _is_xdist_worker(config) or config.option.collectonly:
        return  # workers share the controller's prepared backend; collect-only needs no backend
    cfg = load_config()

    unknown = sorted(set(cfg.enabled_bugs) - set(KNOWN_BUGS))
    if unknown:
        pytest.exit(f"ENABLE_BUGS contains unknown switch(es): {unknown}", returncode=4)

    try:
        waited = wait_for_health(cfg)
    except TimeoutError as exc:
        pytest.exit(str(exc), returncode=3)
    _write(config, f"Backend healthy after {waited:.1f}s")

    if cfg.reset_before_run:
        response = httpx.post(
            f"{cfg.api_base_url}/test/reset", headers={"X-Test-Token": cfg.test_token}, timeout=60
        )
        if response.status_code != 200:
            pytest.exit(
                f"Reset failed: HTTP {response.status_code} {response.text[:200]} "
                "(is TEST_TOKEN correct?)",
                returncode=3,
            )
        _write(config, f"Store reset to seed state: {response.json()}")


def _test_info(item: pytest.Item) -> dict:
    function = getattr(item, "function", None)
    doc = (function.__doc__ or "").strip() if function else ""
    feature = item.get_closest_marker("feature")
    return {
        "id": item.nodeid,
        "name": item.name,
        "file": item.location[0].replace("\\", "/"),
        "layer": next((m for m in LAYERS if item.get_closest_marker(m)), None),
        "layers_declared": [m for m in LAYERS if item.get_closest_marker(m)],
        "feature": feature.args[0] if feature and feature.args else None,
        "bugs": [m.args[0] for m in item.iter_markers("bug") if m.args],
        "docstring": doc,
    }


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    problems = []
    for item in items:
        info = _test_info(item)
        if len(info["layers_declared"]) != 1:
            problems.append(f"{item.nodeid}: needs exactly one of {LAYERS}")
        if not info["feature"]:
            problems.append(f'{item.nodeid}: missing @pytest.mark.feature("...")')
        if not info["docstring"]:
            problems.append(f"{item.nodeid}: missing one-sentence docstring")
        for bug in info["bugs"]:
            if bug not in KNOWN_BUGS:
                problems.append(f"{item.nodeid}: unknown bug switch '{bug}'")
    if problems:
        raise pytest.UsageError("Test metadata problems:\n  " + "\n  ".join(problems))

    out = config.getoption("--catalog-out")
    if out and not _is_xdist_worker(config):
        catalog = [
            {k: v for k, v in _test_info(i).items() if k != "layers_declared"} for i in items
        ]
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(catalog, indent=2), encoding="utf-8")


@pytest.fixture(scope="session")
def run_config() -> RunConfig:
    return load_config()


@pytest.fixture(autouse=True)
def _allure_labels(request: pytest.FixtureRequest) -> None:
    """Group the Allure report by layer and feature, and tag the bug switch a test targets."""
    info = _test_info(request.node)
    if info["layer"]:
        allure.dynamic.epic(info["layer"].upper())
    if info["feature"]:
        allure.dynamic.feature(info["feature"])
    for bug in info["bugs"]:
        allure.dynamic.tag(f"bug:{bug}")
