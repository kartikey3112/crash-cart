"""The dashboard's data directory across runs: index, per-run files, flaky analysis, retention.

Layout (relative to the site root):
  data/runs/index.json        newest-first list of run summaries
  data/runs/<run_id>.json     full record of one run
  data/catalog.json           every test with its docstring and markers
  data/flaky.json             flaky-test analysis
  reports/<run_id>/...        downloads (only for the newest N runs)
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from pipeline.run_record import summary_of

FLIP_WINDOW_DAYS = 30


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def parse_time(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def save_run(site: Path, run: dict) -> list[dict]:
    """Write the run file and insert/replace its summary in the index (newest first)."""
    runs_dir = site / "data" / "runs"
    write_json(runs_dir / f"{run['id']}.json", run)
    index = [r for r in read_json(runs_dir / "index.json", []) if r["id"] != run["id"]]
    index.append(summary_of(run))
    index.sort(key=lambda r: parse_time(r["timestamp"]), reverse=True)
    write_json(runs_dir / "index.json", index)
    return index


def apply_retention(site: Path, keep: int) -> list[str]:
    """Keep full reports for the newest `keep` runs; older runs keep only their summary
    data (statuses stay, so history and flaky analysis still work). Returns pruned run ids."""
    runs_dir = site / "data" / "runs"
    index = read_json(runs_dir / "index.json", [])
    pruned = []
    for summary in index[keep:]:
        report_dir = site / "reports" / summary["id"]
        if not summary.get("reports") and not report_dir.exists():
            continue
        shutil.rmtree(report_dir, ignore_errors=True)
        summary["reports"] = {}
        run_path = runs_dir / f"{summary['id']}.json"
        run = read_json(run_path, None)
        if run is not None:
            run["reports"] = {}
            for test in run["tests"]:
                test["artifacts"] = []
            write_json(run_path, run)
        pruned.append(summary["id"])
    write_json(runs_dir / "index.json", index)
    return pruned


def _outcome(status: str) -> str | None:
    """Final pass/fail for comparisons; skipped tests say nothing about flakiness."""
    if status in ("passed", "flaky"):
        return "pass"
    if status in ("failed", "error"):
        return "fail"
    return None


def compute_flaky(site: Path) -> dict:
    """Two signals, using only runs WITHOUT injected bugs (those failures are deliberate):
      1. same-commit conflicts: a test passed in one run and failed in another on the same SHA
      2. retry-flaky: a test failed and then passed on retry within one run
    Plus a 30-day flip rate: status changes between consecutive runs / (runs - 1)."""
    runs_dir = site / "data" / "runs"
    index = read_json(runs_dir / "index.json", [])
    clean = [s for s in index if not s.get("enabled_bugs")]
    clean.sort(key=lambda s: parse_time(s["timestamp"]))  # oldest first
    newest = parse_time(clean[-1]["timestamp"]) if clean else None

    history: dict[str, dict] = {}
    for summary in clean:
        run = read_json(runs_dir / f"{summary['id']}.json", None)
        if run is None:
            continue
        when = parse_time(run["timestamp"])
        for test in run["tests"]:
            entry = history.setdefault(
                test["id"],
                {"name": test["name"], "layer": test["layer"], "feature": test["feature"],
                 "by_sha": {}, "retry_flaky_runs": [], "timeline": []},
            )  # fmt: skip
            outcome = _outcome(test["status"])
            if test["status"] == "flaky":
                entry["retry_flaky_runs"].append(run["id"])
            if outcome:
                entry["by_sha"].setdefault(run["commit_sha"], {"pass": [], "fail": []})[
                    outcome
                ].append(run["id"])
                entry["timeline"].append((when, outcome, run["id"]))

    tests = []
    for test_id, entry in history.items():
        conflicts = [
            {"commit_sha": sha, "passed_runs": runs["pass"], "failed_runs": runs["fail"]}
            for sha, runs in entry["by_sha"].items()
            if runs["pass"] and runs["fail"]
        ]
        window = [
            o for when, o, _ in entry["timeline"]
            if newest - when <= timedelta(days=FLIP_WINDOW_DAYS)
        ]  # fmt: skip
        flips = sum(1 for a, b in zip(window, window[1:], strict=False) if a != b)
        flip_rate = round(flips / (len(window) - 1), 3) if len(window) > 1 else 0.0
        if conflicts or entry["retry_flaky_runs"] or flips:
            tests.append(
                {
                    "id": test_id,
                    "name": entry["name"],
                    "layer": entry["layer"],
                    "feature": entry["feature"],
                    "same_commit_conflicts": conflicts,
                    "retry_flaky_runs": entry["retry_flaky_runs"],
                    "flips_30d": flips,
                    "runs_30d": len(window),
                    "flip_rate_30d": flip_rate,
                    "last_status": entry["timeline"][-1][1] if entry["timeline"] else None,
                }
            )
    tests.sort(key=lambda t: (-t["flip_rate_30d"], -len(t["retry_flaky_runs"]), t["id"]))
    flaky = {
        "generated_at": newest.isoformat() if newest else None,
        "window_days": FLIP_WINDOW_DAYS,
        "runs_considered": len(clean),
        "runs_excluded_with_bugs": len(index) - len(clean),
        "tests": tests,
    }
    write_json(site / "data" / "flaky.json", flaky)
    return flaky


def save_catalog(site: Path, catalog: dict[str, dict], generated_at: str) -> None:
    entries = sorted(catalog.values(), key=lambda e: (e["layer"], e["feature"], e["id"]))
    write_json(site / "data" / "catalog.json", {"generated_at": generated_at, "tests": entries})
