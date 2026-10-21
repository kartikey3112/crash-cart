import pytest

from pipeline.ci_plan import PlanError, plan, to_outputs
from pipeline.ci_wait import commit_matches, wait_until


@pytest.mark.parametrize("event", ["push", "schedule"])
def test_automatic_runs_use_everything_on_chromium(event):
    """Push and nightly runs test every live suite on Chromium with no bug switches."""
    result = plan(event, has_urls=True, suites="api", browsers="firefox", bugs="order_idor")
    assert (result["run_api"], result["run_ui"], result["run_perf"]) == (True, True, True)
    assert (result["browsers"], result["bugs"]) == (["chromium"], "")


def test_manual_run_uses_inputs_in_a_fixed_order():
    """A manual run uses its inputs, normalised: lower case, known order."""
    result = plan(
        "workflow_dispatch", True, "UI, api", "webkit,chromium", "sort_desc_broken,cart_rounding"
    )
    assert (result["run_api"], result["run_ui"], result["run_perf"]) == (True, True, False)
    assert result["browsers"] == ["chromium", "webkit"]
    assert result["bugs"] == "cart_rounding,sort_desc_broken"


@pytest.mark.parametrize(
    ("suites", "browsers", "bugs", "message"),
    [
        ("api,load", "chromium", "", "unknown suite"),
        ("ui", "safari", "", "unknown browser"),
        ("api", "chromium", "cart_roundng", "unknown bug switch"),
        ("ui", "", "", "needs at least one browser"),
    ],
)
def test_manual_run_rejects_typos(suites, browsers, bugs, message):
    """Typos in manual-run inputs fail the run instead of silently testing less."""
    with pytest.raises(PlanError, match=message):
        plan("workflow_dispatch", True, suites, browsers, bugs)


def test_browser_list_is_never_empty():
    """A manual API-only run with no browsers still outputs a valid (unused) browser list."""
    result = plan("workflow_dispatch", True, "api", "", "")
    assert result["browsers"] == ["chromium"] and result["run_ui"] is False


def test_live_testing_is_skipped_until_urls_exist():
    """Before deployment (no URL secrets) nothing live runs, with the reason given."""
    result = plan("push", has_urls=False)
    assert result["live"] is False and result["run_api"] is False
    assert result["reason"] == "live URLs not configured"


def test_outputs_are_github_style():
    """Outputs are key=value lines; booleans lower-case, browsers as a JSON array."""
    text = to_outputs(plan("push", True))
    assert "run_ui=true" in text and 'browsers=["chromium"]' in text


@pytest.mark.parametrize(
    ("reported", "expected", "matches"),
    [
        ("abc123def456", "abc123def456", True),
        ("abc123d", "abc123def456", True),  # short SHA reported
        ("abc123def456", "abc123d", True),
        ("fff000", "abc123def456", False),
        ("unknown", "abc123def456", False),
        (None, "abc123def456", False),
        ("", "abc123def456", False),
    ],
)
def test_commit_matching(reported, expected, matches):
    """A deploy counts as current only when it reports the pushed commit (full or short SHA)."""
    assert commit_matches(reported, expected) is matches


def fake_clock(step: int):
    """A clock that advances `step` seconds per reading, so no test ever really sleeps."""
    ticks = iter(range(0, 10_000, step))
    return lambda: next(ticks)


def test_wait_until_retries_then_succeeds():
    """wait_until keeps checking through 'not ready' and errors until the check passes."""
    answers = iter([False, OSError("refused"), True])

    def check():
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    # Clock readings: 0 (start), 5/10/15 (loop checks; the 3rd check passes), 20 (return value).
    assert wait_until(check, 60, 5, "backend", clock=fake_clock(5), sleep=lambda s: None) == 20


def test_wait_until_times_out_with_last_error():
    """When the check never passes, the timeout error includes the last failure."""

    def check():
        raise OSError("connection refused")

    with pytest.raises(TimeoutError, match="connection refused"):
        wait_until(check, 30, 10, "backend", clock=fake_clock(10), sleep=lambda s: None)
