"""Assemble one run's record: metadata, per-test results, per-layer counts, perf, coverage."""

from dataclasses import dataclass

from pipeline.inputs import browser_of, catalog_entry
from pipeline.junit import TestResult

STATUSES = ("passed", "failed", "error", "skipped", "flaky")
LAYERS = ("unit", "api", "ui", "perf")


@dataclass(frozen=True)
class RunMeta:
    run_id: str
    timestamp: str  # ISO 8601, UTC
    commit_sha: str
    branch: str
    trigger: str  # push | schedule | workflow_dispatch | local
    enabled_bugs: tuple[str, ...] = ()
    workflow_url: str = ""


def count(tests: list[dict]) -> dict:
    counts = {status: 0 for status in STATUSES}
    for test in tests:
        counts[test["status"]] += 1
    counts["total"] = len(tests)
    executed = counts["total"] - counts["skipped"]
    # A flaky test did pass in the end, so it counts toward the pass rate.
    counts["pass_rate"] = (
        round((counts["passed"] + counts["flaky"]) / executed * 100, 1) if executed else None
    )
    return counts


def build_run(
    meta: RunMeta,
    results: list[TestResult],
    catalog: dict[str, dict],
    suite_seconds: dict[str, float],
    perf: list[dict],
    coverage: dict | None,
) -> dict:
    tests = []
    for result in results:
        entry = catalog_entry(catalog, result.test_id) or {}
        tests.append(
            {
                "id": result.test_id,
                "name": result.name,
                "layer": entry.get("layer") or "unknown",
                "feature": entry.get("feature") or "unknown",
                "bugs": entry.get("bugs", []),
                "browser": browser_of(result.test_id),
                "status": result.status,
                "duration_s": result.duration_s,
                "attempts": result.attempts,
                "message": result.message,
                "artifacts": result.artifacts,
            }
        )

    layers_present = [layer for layer in LAYERS if any(t["layer"] == layer for t in tests)]
    return {
        "id": meta.run_id,
        "timestamp": meta.timestamp,
        "commit_sha": meta.commit_sha,
        "branch": meta.branch,
        "trigger": meta.trigger,
        "enabled_bugs": list(meta.enabled_bugs),
        "workflow_url": meta.workflow_url,
        "duration_s": round(sum(suite_seconds.values()), 1),
        "suite_seconds": suite_seconds,
        "counts": count(tests),
        "layers": {
            layer: count([t for t in tests if t["layer"] == layer]) for layer in layers_present
        },
        "tests": tests,
        "perf": perf,
        "coverage": coverage,
        "reports": {},  # filled in by the build step
    }


def summary_of(run: dict) -> dict:
    """The small version of a run that goes into runs/index.json."""
    keys = (
        "id", "timestamp", "commit_sha", "branch", "trigger", "enabled_bugs", "workflow_url",
        "duration_s", "suite_seconds", "counts", "layers", "coverage", "reports",
    )  # fmt: skip
    summary = {key: run[key] for key in keys}
    summary["perf"] = [
        {k: p[k] for k in ("scenario", "p95_ms", "p95_budget_ms", "passed")} for p in run["perf"]
    ]
    return summary
