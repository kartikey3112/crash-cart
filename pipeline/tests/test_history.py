from datetime import datetime, timedelta

from pipeline.history import apply_retention, compute_flaky, read_json, save_run

T0 = datetime(2026, 10, 1, 12, 0, 0)


def make_run(run_id: str, days: float, statuses: dict[str, str], sha="sha1", bugs=()) -> dict:
    tests = [
        {"id": tid, "name": tid, "layer": "api", "feature": "cart", "bugs": [], "browser": None,
         "status": status, "duration_s": 0.1, "attempts": 1, "message": "",
         "artifacts": [{"type": "trace", "path": f"reports/{run_id}/artifacts/t.zip"}]}
        for tid, status in statuses.items()
    ]  # fmt: skip
    return {
        "id": run_id,
        "timestamp": (T0 + timedelta(days=days)).isoformat() + "+00:00",
        "commit_sha": sha,
        "branch": "main",
        "trigger": "push",
        "enabled_bugs": list(bugs),
        "workflow_url": "",
        "duration_s": 1.0,
        "counts": {},
        "layers": {},
        "tests": tests,
        "perf": [],
        "coverage": None,
        "reports": {"pdf": {"path": f"reports/{run_id}/summary.pdf", "bytes": 1}},
    }


def test_index_is_newest_first_and_rebuilds_replace(site):
    """The index lists runs newest first, and saving a run id again replaces it."""
    save_run(site, make_run("old", 0, {"t": "passed"}))
    save_run(site, make_run("new", 1, {"t": "passed"}))
    save_run(site, make_run("old", 0, {"t": "failed"}))
    index = read_json(site / "data/runs/index.json", [])
    assert [r["id"] for r in index] == ["new", "old"]


def test_retention_keeps_reports_only_for_newest_runs(site):
    """With keep=2, the oldest run loses its report folder and artifact links but keeps
    its test statuses."""
    for i in range(3):
        save_run(site, make_run(f"r{i}", i, {"t": "passed"}))
        (site / "reports" / f"r{i}").mkdir(parents=True)
    assert apply_retention(site, keep=2) == ["r0"]
    assert not (site / "reports/r0").exists() and (site / "reports/r2").exists()
    old = read_json(site / "data/runs/r0.json", None)
    assert old["reports"] == {} and old["tests"][0]["artifacts"] == []
    assert old["tests"][0]["status"] == "passed"
    index = {r["id"]: r for r in read_json(site / "data/runs/index.json", [])}
    assert index["r0"]["reports"] == {} and index["r2"]["reports"]
    assert apply_retention(site, keep=2) == []  # already pruned: nothing to do


def test_same_commit_conflict_is_flaky(site):
    """A test that passed and failed on the same commit is reported with both run ids."""
    save_run(site, make_run("a", 0, {"t": "passed", "steady": "passed"}, sha="s1"))
    save_run(site, make_run("b", 1, {"t": "failed", "steady": "passed"}, sha="s1"))
    flaky = compute_flaky(site)
    [entry] = flaky["tests"]
    assert entry["id"] == "t"
    assert entry["same_commit_conflicts"] == [
        {"commit_sha": "s1", "passed_runs": ["a"], "failed_runs": ["b"]}
    ]


def test_runs_with_injected_bugs_are_ignored(site):
    """Failures caused by an enabled bug switch never count as flakiness."""
    save_run(site, make_run("clean", 0, {"t": "passed"}, sha="s1"))
    save_run(site, make_run("bugged", 1, {"t": "failed"}, sha="s1", bugs=["cart_rounding"]))
    flaky = compute_flaky(site)
    assert flaky["tests"] == []
    assert (flaky["runs_considered"], flaky["runs_excluded_with_bugs"]) == (1, 1)


def test_pass_on_retry_is_reported(site):
    """A test with status 'flaky' in any run is listed under retry_flaky_runs."""
    save_run(site, make_run("a", 0, {"t": "flaky"}))
    [entry] = compute_flaky(site)["tests"]
    assert entry["retry_flaky_runs"] == ["a"]


def test_flip_rate_uses_only_the_last_30_days(site):
    """Flip rate = status changes / (runs - 1) over runs in the 30 days before the newest run."""
    save_run(site, make_run("ancient", 0, {"t": "failed"}, sha="s0"))  # 40 days before newest
    for i, status in enumerate(["passed", "failed", "passed", "passed"]):
        save_run(site, make_run(f"r{i}", 37 + i, {"t": status}, sha=f"s{i + 1}"))
    [entry] = compute_flaky(site)["tests"]
    assert (entry["runs_30d"], entry["flips_30d"], entry["flip_rate_30d"]) == (4, 2, 0.667)
