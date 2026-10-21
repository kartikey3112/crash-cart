import json
import zipfile
from pathlib import Path

import pytest

from pipeline import build
from pipeline.history import read_json
from pipeline.pdf_summary import latin1, render_summary
from pipeline.reports import allure_command, allure_report_zip


def run_build(raw: Path, site: Path, run_id: str, **extra) -> dict:
    argv = ["--raw", str(raw), "--site", str(site), "--run-id", run_id, "--sha", "abc123def",
            "--timestamp", extra.pop("timestamp", "2026-10-21T10:00:00+00:00")]  # fmt: skip
    for key, value in extra.items():
        argv += [f"--{key.replace('_', '-')}", str(value)]
    return build.build(build.parse_args(argv))


def test_end_to_end_build_writes_all_dashboard_files(raw, site):
    """One build produces the run file, index, catalog, flaky file and downloads."""
    run = run_build(raw, site, "run-1", dashboard_url="https://example.test/dash")

    assert (run["counts"]["total"], run["counts"]["flaky"]) == (10, 1)
    assert set(run["layers"]) == {"unit", "api-local", "api", "ui"}
    assert run["coverage"]["percent"] == 98.2 and run["perf"][0]["scenario"] == "products_list"
    assert read_json(site / "data/runs/index.json", [])[0]["id"] == "run-1"
    assert len(read_json(site / "data/catalog.json", {})["tests"]) == 7
    assert read_json(site / "data/flaky.json", {})["tests"][0]["retry_flaky_runs"] == ["run-1"]
    assert set(run["reports"]) == {"junit", "pdf"}  # no Allure CLI in this test


def test_artifacts_are_copied_and_relinked(raw, site):
    """Traces/screenshots are copied into reports/<run>/artifacts and linked from the site
    root; links to files that don't exist are dropped."""
    run = run_build(raw, site, "run-1")
    sort = next(t for t in run["tests"] if t["id"].endswith("test_sort[chromium]"))
    paths = [a["path"] for a in sort["artifacts"]]
    assert paths == [
        "reports/run-1/artifacts/test-results/sort/trace.zip",
        "reports/run-1/artifacts/test-results/sort-retry1/trace.zip",
    ]
    assert all((site / p).is_file() for p in paths)


def test_junit_zip_contains_every_input_file(raw, site):
    """The JUnit download holds each raw JUnit XML file."""
    run_build(raw, site, "run-1")
    with zipfile.ZipFile(site / "reports/run-1/junit.zip") as archive:
        assert sorted(archive.namelist()) == [
            "junit-api-local.xml", "junit-api.xml", "junit-ui-chromium.xml", "junit-unit.xml",
        ]  # fmt: skip


def test_in_runner_api_results_stay_separate_from_live_ones(raw, site):
    """The same API test run against the in-runner backend and the live store gives two
    results: the local one is prefixed, has its own layer, and still finds its catalog entry."""
    run = run_build(raw, site, "run-1")
    live = [t for t in run["tests"] if t["id"] == "tests/api/test_cart.py::test_totals[one-cable]"]
    local = [
        t for t in run["tests"] if t["id"] == "local:tests/api/test_cart.py::test_totals[one-cable]"
    ]
    assert [t["status"] for t in live] == ["failed"]
    assert [(t["status"], t["layer"], t["feature"], t["bugs"]) for t in local] == [
        ("passed", "api-local", "cart", ["cart_rounding"])
    ]
    assert run["layers"]["api-local"]["total"] == 2 and run["layers"]["api"]["total"] == 4


def test_second_build_adds_to_history(raw, site):
    """Building a second run keeps the first one in the index."""
    run_build(raw, site, "run-1", timestamp="2026-10-21T10:00:00+00:00")
    run_build(raw, site, "run-2", timestamp="2026-10-21T11:00:00+00:00", bugs="cart_rounding")
    index = read_json(site / "data/runs/index.json", [])
    assert [r["id"] for r in index] == ["run-2", "run-1"]
    assert index[0]["enabled_bugs"] == ["cart_rounding"]


def test_build_without_junit_fails_clearly(raw, site):
    """A raw folder with no JUnit results stops the build with a clear message."""
    for path in (raw / "junit").glob("*.xml"):
        path.unlink()
    with pytest.raises(SystemExit, match="No JUnit results"):
        run_build(raw, site, "run-1")


def test_pdf_stays_on_one_page_with_many_failures(tmp_path):
    """Even with 40 failures and non-Latin text the summary renders on exactly one page."""
    tests = [
        {"id": f"tests/api/test_x.py::test_{i}", "layer": "api", "status": "failed",
         "message": "AssertionError: ₹ price mismatch ✓ " + "x" * 200}
        for i in range(40)
    ]  # fmt: skip
    counts = {"total": 40, "passed": 0, "failed": 40, "error": 0, "skipped": 0, "flaky": 0,
              "pass_rate": 0.0}  # fmt: skip
    run = {"id": "r", "timestamp": "2026-10-21T10:00:00+00:00", "commit_sha": "abc",
           "branch": "main", "trigger": "push", "duration_s": 1.0, "enabled_bugs": ["x"],
           "counts": counts, "layers": {"api": counts}, "tests": tests, "perf": [],
           "coverage": None}  # fmt: skip
    assert render_summary(run, tmp_path / "s.pdf", "https://example.test") == 1
    assert (tmp_path / "s.pdf").read_bytes().startswith(b"%PDF")
    assert latin1("₹5 ✓") == "?5 ?"


def test_allure_report_is_generated_when_cli_available(raw, tmp_path, monkeypatch):
    """With a real Allure CLI and results, the report zip contains index.html."""
    monkeypatch.delenv("ALLURE_CMD")
    if allure_command() is None:
        pytest.skip("Allure CLI not installed on this machine")
    results = tmp_path / "allure-results"
    results.mkdir()
    (results / "1-result.json").write_text(
        json.dumps({"uuid": "1", "historyId": "h1", "name": "sample", "status": "passed",
                    "start": 1, "stop": 2}),
        encoding="utf-8",
    )  # fmt: skip
    out = allure_report_zip(results, tmp_path / "allure-report.zip")
    with zipfile.ZipFile(out) as archive:
        assert "index.html" in archive.namelist()
