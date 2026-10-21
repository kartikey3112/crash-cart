"""Loaders for the other raw inputs: test catalogs, perf summaries and coverage."""

import json
import re
from pathlib import Path

BROWSER_PARAM = re.compile(r"\[(chromium|firefox|webkit)\]$")
PERF_STATS = (
    "samples", "errors", "error_rate", "p50_ms", "p95_ms", "p99_ms", "max_ms", "throughput_rps",
)  # fmt: skip


def load_catalog(paths: list[Path]) -> dict[str, dict]:
    """Merge catalog files (from --catalog-out) into {test id: entry}."""
    catalog: dict[str, dict] = {}
    for path in paths:
        for entry in json.loads(path.read_text(encoding="utf-8")):
            catalog[entry["id"]] = entry
    return catalog


def catalog_entry(catalog: dict[str, dict], test_id: str) -> dict | None:
    """Exact match, else the same UI test collected for Chromium (catalogs are collected
    once, but nightly runs repeat UI tests on Firefox and WebKit)."""
    if test_id in catalog:
        return catalog[test_id]
    return catalog.get(BROWSER_PARAM.sub("[chromium]", test_id))


def browser_of(test_id: str) -> str | None:
    match = BROWSER_PARAM.search(test_id)
    return match.group(1) if match else None


def load_perf(perf_dir: Path | None) -> list[dict]:
    """Scenario summaries written by tests/perf (one JSON per scenario)."""
    if not perf_dir or not perf_dir.is_dir():
        return []
    summaries = []
    for path in sorted(perf_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "scenario" in data and "stats" in data:
            summaries.append(
                {
                    "scenario": data["scenario"],
                    "path": data["path"],
                    "p95_budget_ms": data["p95_budget_ms"],
                    "passed": data["passed"],
                    "profile": data["profile"],
                    **{key: data["stats"][key] for key in PERF_STATS},
                }
            )
    return summaries


def load_coverage(path: Path | None) -> dict | None:
    """Totals from `coverage json` output."""
    if not path or not path.exists():
        return None
    totals = json.loads(path.read_text(encoding="utf-8"))["totals"]
    return {
        "percent": round(totals["percent_covered"], 1),
        "lines_covered": totals["covered_lines"],
        "lines_total": totals["num_statements"],
        "branches_covered": totals.get("covered_branches"),
        "branches_total": totals.get("num_branches"),
    }
