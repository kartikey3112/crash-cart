import json

from playwright.sync_api import Page, expect

from dashboard.tests.fixture_site import BUG_RUN, CLEAN_RUN


def test_run_history_lists_newest_first_and_filters(page: Page):
    """Run history lists both runs newest first, and the bug filter narrows it to one."""
    page.goto("/runs.html")
    rows = page.get_by_test_id("run-row")
    expect(rows).to_have_count(2)
    assert [r.get_attribute("data-run-id") for r in rows.all()] == [BUG_RUN, CLEAN_RUN]
    page.get_by_test_id("filter-kind").select_option("bugs")
    expect(rows).to_have_count(1)
    expect(page.get_by_test_id("run-count")).to_have_text("1 of 2 runs")
    page.get_by_test_id("filter-kind").select_option("clean")
    expect(rows).to_have_attribute("data-run-id", CLEAN_RUN)


def test_failed_filter_shows_failures_and_errors(page: Page):
    """?status=failed lists the 2 failed and 1 errored system tests, with their messages."""
    page.goto(f"/run.html?id={BUG_RUN}&status=failed")
    system = page.get_by_test_id("system-tests")
    expect(system.get_by_test_id("test-row")).to_have_count(3)
    expect(system).to_contain_text("AssertionError: assert 1577 == 1578")


def test_ui_failure_links_to_existing_artifacts(page: Page, base_url: str):
    """A failed UI test links its traces, and every linked artifact actually downloads."""
    page.goto(f"/run.html?id={BUG_RUN}&status=failed")
    row = page.get_by_test_id("test-row").filter(has_text="test_sort[chromium]")
    links = row.locator("a.pill")
    # Two attempts, each with its own trace, labelled by attempt number.
    expect(row.get_by_text("open in Trace Viewer 1")).to_be_visible()
    expect(row.get_by_text("open in Trace Viewer 2")).to_be_visible()
    hrefs = [
        link.get_attribute("href")
        for link in links.all()
        if "trace.playwright.dev" not in (link.get_attribute("href") or "")
    ]
    assert hrefs, "expected artifact links"
    for href in hrefs:
        assert page.request.get(f"{base_url}/{href}").ok, href


def test_layer_tabs_and_search(page: Page):
    """The UI tab shows only UI tests, and the search box narrows by name."""
    page.goto(f"/run.html?id={CLEAN_RUN}")
    system = page.get_by_test_id("system-tests")
    page.get_by_test_id("tab-ui").click()
    expect(system.get_by_test_id("test-row")).to_have_count(3)
    system.get_by_test_id("test-search").fill("badge")
    expect(system.get_by_test_id("test-row")).to_have_count(1)
    expect(system.get_by_test_id("test-row").get_by_test_id("status")).to_have_text("Flaky")


def test_unit_tests_are_a_separate_section(page: Page):
    """Unit tests appear in their own section with coverage, not mixed into system tests."""
    page.goto(f"/run.html?id={CLEAN_RUN}")
    unit = page.get_by_test_id("unit-tests")
    expect(unit).to_contain_text("Backend unit tests")
    expect(unit.get_by_test_id("coverage")).to_contain_text("98.2%")
    expect(unit.get_by_test_id("test-row")).to_have_count(1)
    expect(page.get_by_test_id("system-tests")).not_to_contain_text("test_to_cents_rounds_half_up")


def test_in_runner_api_results_are_a_separate_section(page: Page):
    """The CI self-test's API results get their own section and never mix into the system
    tests, even though they share test names with the live API suite."""
    page.goto(f"/run.html?id={CLEAN_RUN}")
    local = page.get_by_test_id("api-local-tests")
    expect(local).to_contain_text("API suite against an in-runner backend")
    expect(local.get_by_test_id("test-row")).to_have_count(2)
    expect(
        local.get_by_test_id("test-row").filter(has_text="test_totals[one-cable]")
    ).to_contain_text("Passed")
    system = page.get_by_test_id("system-tests")
    expect(system.get_by_test_id("test-row")).to_have_count(7)  # 4 live API + 3 UI only
    expect(system).not_to_contain_text("local:tests/api")


def test_unknown_run_shows_error(page: Page):
    """Opening a run id that doesn't exist shows an error message."""
    page.goto("/run.html?id=no-such-run")
    expect(page.get_by_test_id("load-error")).to_contain_text("HTTP 404")


def test_test_names_are_rendered_as_text_not_html(page: Page):
    """Markup inside a test name or error message is shown as text and never executed."""
    payload = '<img src=x onerror="window.__pwned=1">'

    def poisoned(route):
        run = json.loads(route.fetch().text())
        run["tests"][0]["name"] = payload
        run["tests"][0]["message"] = f"<script>window.__pwned=1</script>{payload}"
        route.fulfill(json=run)

    page.route(f"**/data/runs/{CLEAN_RUN}.json", poisoned)
    page.goto(f"/run.html?id={CLEAN_RUN}")
    expect(page.get_by_text(payload).first).to_be_visible()
    assert page.locator("main img[src='x']").count() == 0
    assert page.evaluate("window.__pwned") is None
