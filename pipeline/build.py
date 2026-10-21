"""Build step: raw test outputs for ONE run -> updated dashboard data + downloads.

Expected raw layout (what CI collects; any part may be missing):
  raw/junit/*.xml             JUnit files. A file named junit-unit*.xml holds backend unit tests.
  raw/catalog/*.json          --catalog-out files (system tests + unit tests)
  raw/perf/*.json             perf scenario summaries
  raw/allure-results/         allure-pytest output (all suites)
  raw/coverage.json           `coverage json` output for the backend
  raw/test-results/...        Playwright traces/screenshots referenced from JUnit

Usage:
  python -m pipeline.build --raw raw --site site --run-id 123-1 --sha abc123 \
      --branch main --trigger push [--bugs a,b] [--keep 30] [--dashboard-url URL]
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from pipeline import history, inputs, junit, reports
from pipeline.pdf_summary import render_summary
from pipeline.run_record import LOCAL_ID_PREFIX, RunMeta, build_run

# JUnit file name prefix -> id prefix, so results from different targets never share ids.
ID_PREFIXES = {
    "junit-unit": "store/backend/",  # backend unit tests (paths relative to store/backend)
    "junit-api-local": LOCAL_ID_PREFIX,  # API suite against the in-runner backend
}


def id_prefix_for(filename: str) -> str:
    return next((p for start, p in ID_PREFIXES.items() if filename.startswith(start)), "")


def collect_results(junit_dir: Path) -> tuple[list[junit.TestResult], dict[str, float]]:
    results, seconds = [], {}
    for path in sorted(junit_dir.glob("*.xml")) if junit_dir.is_dir() else []:
        prefix = id_prefix_for(path.name)
        results += junit.fold_retries(junit.parse_attempts(path, prefix))
        seconds[path.stem.removeprefix("junit-")] = junit.suite_seconds(path)
    return results, seconds


def build(args: argparse.Namespace) -> dict:
    raw, site = Path(args.raw), Path(args.site)
    meta = RunMeta(
        run_id=args.run_id,
        timestamp=args.timestamp or datetime.now(UTC).isoformat(timespec="seconds"),
        commit_sha=args.sha,
        branch=args.branch,
        trigger=args.trigger,
        enabled_bugs=tuple(b for b in args.bugs.split(",") if b),
        workflow_url=args.workflow_url,
    )

    catalog = inputs.load_catalog(sorted((raw / "catalog").glob("*.json")))
    results, seconds = collect_results(raw / "junit")
    if not results:
        raise SystemExit(f"No JUnit results found under {raw / 'junit'}")
    run = build_run(
        meta,
        results,
        catalog,
        seconds,
        inputs.load_perf(raw / "perf"),
        inputs.load_coverage(raw / "coverage.json"),
    )

    report_dir = site / "reports" / meta.run_id
    downloads = {}
    reports.copy_artifacts(run["tests"], raw, report_dir, site)
    junit_files = sorted((raw / "junit").glob("*.xml"))
    downloads["junit"] = reports.zip_files(junit_files, report_dir / "junit.zip", raw / "junit")
    pages = render_summary(run, report_dir / "summary.pdf", args.dashboard_url)
    downloads["pdf"] = report_dir / "summary.pdf"
    if allure_zip := reports.allure_report_zip(
        raw / "allure-results", report_dir / "allure-report.zip"
    ):
        downloads["allure"] = allure_zip
    run["reports"] = {
        kind: {"path": path.relative_to(site).as_posix(), "bytes": path.stat().st_size}
        for kind, path in downloads.items()
    }

    history.save_run(site, run)
    if catalog:
        history.save_catalog(site, catalog, meta.timestamp)
    pruned = history.apply_retention(site, args.keep)
    flaky = history.compute_flaky(site)

    c = run["counts"]
    print(
        f"Run {meta.run_id}: {c['total']} tests, {c['passed']} passed, {c['failed']} failed, "
        f"{c['error']} errors, {c['skipped']} skipped, {c['flaky']} flaky; "
        f"downloads: {', '.join(run['reports'])}; PDF pages: {pages}; "
        f"pruned reports: {len(pruned)}; flaky tests tracked: {len(flaky['tests'])}"
    )
    return run


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dashboard data for one test run.")
    parser.add_argument("--raw", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--trigger", default="local")
    parser.add_argument("--timestamp", default="", help="ISO 8601 UTC; default: now")
    parser.add_argument("--bugs", default="", help="bug switches enabled in this run")
    parser.add_argument("--workflow-url", default="")
    parser.add_argument("--dashboard-url", default="")
    parser.add_argument("--keep", type=int, default=30, help="runs that keep full reports")
    return parser.parse_args(argv)


if __name__ == "__main__":
    build(parse_args(sys.argv[1:]))
