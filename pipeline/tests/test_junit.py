import pytest

from pipeline.junit import artifact_path, fold_retries, node_id, parse_attempts, suite_seconds


def by_id(results):
    return {r.test_id: r for r in results}


def test_statuses_and_first_line_messages(raw):
    """Pass, failure, error and skip are read correctly, keeping only the first message line."""
    results = by_id(fold_retries(parse_attempts(raw / "junit" / "junit-api.xml")))
    assert results["tests/api/test_cart.py::test_add_item"].status == "passed"
    failed = results["tests/api/test_cart.py::test_totals[one-cable]"]
    assert (failed.status, failed.message) == ("failed", "AssertionError: assert 1577 == 1578")
    assert results["tests/api/test_orders.py::test_history"].status == "error"
    assert results["tests/api/test_admin.py::test_skipped_one"].status == "skipped"


def test_pass_on_retry_is_flaky_with_all_attempt_artifacts(raw):
    """A test that failed then passed on retry is 'flaky', with 2 attempts and the first
    attempt's trace and screenshot kept."""
    results = by_id(fold_retries(parse_attempts(raw / "junit" / "junit-ui-chromium.xml")))
    flaky = results["tests/ui/test_cart_ui.py::test_badge[chromium]"]
    assert (flaky.status, flaky.attempts) == ("flaky", 2)
    assert {a["type"] for a in flaky.artifacts} == {"trace", "screenshot"}
    assert all("\\" not in a["path"] for a in flaky.artifacts)


def test_fail_on_every_attempt_is_failed(raw):
    """A test that failed on both attempts is 'failed', with durations summed."""
    results = by_id(fold_retries(parse_attempts(raw / "junit" / "junit-ui-chromium.xml")))
    failed = results["tests/ui/test_catalog_ui.py::test_sort[chromium]"]
    assert (failed.status, failed.attempts, failed.duration_s) == ("failed", 2, 1.7)
    assert failed.message == "AssertionError: prices not descending"


def test_unit_ids_get_repo_prefix(raw):
    """Backend unit test ids are prefixed so they're unique across the repo."""
    [attempt] = parse_attempts(raw / "junit" / "junit-unit.xml", "store/backend/")
    assert attempt.test_id == "store/backend/tests/test_pricing.py::test_to_cents_rounds_half_up"


@pytest.mark.parametrize(
    "value",
    [
        r"test-results\badge\trace.zip",
        r"D:\CrashCart\raw\test-results\badge\trace.zip",
        "/home/runner/work/crash-cart/raw/test-results/badge/trace.zip",
    ],
    ids=["relative", "windows-absolute", "ci-absolute"],
)
def test_artifact_paths_are_normalised(value):
    """Wherever pytest ran, artifact paths become 'test-results/...' relative paths."""
    assert artifact_path(value) == "test-results/badge/trace.zip"


def test_node_id_rebuilds_pytest_ids():
    """JUnit classname + name map back to the pytest node id."""
    assert node_id("tests.api.test_cart", "test_x[a-b]") == "tests/api/test_cart.py::test_x[a-b]"


def test_suite_seconds(raw):
    """The suite's wall time comes from the <testsuite time> attribute."""
    assert suite_seconds(raw / "junit" / "junit-api.xml") == 12.5
