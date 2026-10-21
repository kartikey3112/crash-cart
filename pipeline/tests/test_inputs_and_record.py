from pipeline.inputs import browser_of, catalog_entry, load_catalog, load_coverage, load_perf
from pipeline.junit import TestResult
from pipeline.run_record import RunMeta, build_run, count


def result(test_id: str, status: str) -> TestResult:
    return TestResult(test_id, test_id.split("::")[-1], status, 0.1, 1, "", [])


def test_catalog_falls_back_to_chromium_id(raw):
    """A Firefox run of a UI test finds the catalog entry collected for Chromium."""
    catalog = load_catalog(sorted((raw / "catalog").glob("*.json")))
    entry = catalog_entry(catalog, "tests/ui/test_catalog_ui.py::test_sort[firefox]")
    assert entry["feature"] == "catalog"
    assert browser_of("tests/ui/test_catalog_ui.py::test_sort[firefox]") == "firefox"
    assert catalog_entry(catalog, "tests/api/test_nope.py::test_missing") is None


def test_perf_summaries_are_flattened_and_other_json_ignored(raw):
    """Perf summaries become flat rows; unrelated JSON files in the folder are skipped."""
    [row] = load_perf(raw / "perf")
    assert (row["scenario"], row["p95_ms"], row["p95_budget_ms"], row["passed"]) == (
        "products_list", 29, 800, True,
    )  # fmt: skip
    assert load_perf(raw / "no-such-dir") == []


def test_coverage_totals(raw):
    """Coverage totals are read from `coverage json`; a missing file means no coverage."""
    assert load_coverage(raw / "coverage.json")["percent"] == 98.2
    assert load_coverage(raw / "missing.json") is None


def test_counts_treat_flaky_as_passed_and_ignore_skips():
    """Pass rate = (passed + flaky) / (total - skipped)."""
    tests = [{"status": s} for s in ("passed", "passed", "flaky", "failed", "skipped")]
    counts = count(tests)
    assert (counts["total"], counts["flaky"], counts["pass_rate"]) == (5, 1, 75.0)
    assert count([])["pass_rate"] is None


def test_build_run_groups_layers_and_marks_unknown_tests():
    """Tests are grouped by catalog layer; a test missing from the catalog is 'unknown'."""
    catalog = {"tests/api/a.py::t1": {"layer": "api", "feature": "cart", "bugs": ["x"]}}
    meta = RunMeta("r1", "2026-10-21T10:00:00+00:00", "abc", "main", "local")
    run = build_run(
        meta,
        [result("tests/api/a.py::t1", "passed"), result("tests/other.py::t2", "failed")],
        catalog,
        {"api": 2.0},
        [],
        None,
    )
    assert set(run["layers"]) == {"api"}
    assert run["counts"]["failed"] == 1
    unknown = next(t for t in run["tests"] if t["id"] == "tests/other.py::t2")
    assert (unknown["layer"], unknown["feature"]) == ("unknown", "unknown")
