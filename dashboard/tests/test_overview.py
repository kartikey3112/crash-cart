"""Overview page. Expected numbers come from the sample run (see conftest):
system tests = 7 (1 skipped), 2 passed + 1 flaky of 6 executed -> 50%."""

from playwright.sync_api import Page, expect

from dashboard.tests.fixture_site import BUG_RUN


def open_overview(page: Page) -> None:
    page.goto("/index.html")
    expect(page.get_by_test_id("latest-run")).to_be_visible()


def test_latest_run_card_shows_newest_run_and_verdict(page: Page, console_errors):
    """The latest-run card shows the newest run, its failed verdict and the system pass rate."""
    open_overview(page)
    card = page.get_by_test_id("latest-run")
    expect(card).to_contain_text(BUG_RUN)
    expect(card.get_by_test_id("status")).to_have_text("Failed")
    expect(card).to_contain_text("50%")
    expect(card).to_contain_text("cart_rounding")
    assert console_errors == []


def test_tiles_keep_unit_tests_separate(page: Page):
    """System and unit tests have separate tiles, with coverage and perf summaries."""
    open_overview(page)
    expect(page.get_by_test_id("tile-system")).to_contain_text("3 / 6")
    expect(page.get_by_test_id("tile-unit")).to_contain_text("1 / 1")
    # In-runner API results have their own tile and are NOT in the system "3 / 6" above.
    expect(page.get_by_test_id("tile-api-local")).to_contain_text("2 / 2")
    expect(page.get_by_test_id("tile-coverage")).to_contain_text("98.2%")
    expect(page.get_by_test_id("tile-perf")).to_contain_text("1 / 1")


def test_charts_render_with_table_twins(page: Page):
    """Both trend charts draw a canvas, and each has a table view listing every run."""
    open_overview(page)
    for chart in ("pass-rate-chart", "duration-chart"):
        box = page.get_by_test_id(chart)
        expect(box.locator("canvas")).to_be_visible()
        box.get_by_text("Show as table").click()
        expect(box.locator("tbody tr")).to_have_count(2)


def test_bug_proof_table_reports_caught_switch(page: Page):
    """The injected-bugs table shows cart_rounding caught by its 1 targeted API test."""
    open_overview(page)
    row = page.get_by_test_id("bug-proof").locator("tbody tr")
    expect(row).to_have_count(1)
    expect(row).to_contain_text("cart_rounding")
    expect(row).to_contain_text("1 / 1")
    expect(row).to_contain_text("Caught")


def test_charts_degrade_gracefully_when_cdn_is_blocked(page: Page):
    """If the Chart.js CDN is unreachable, the data still renders with a clear note."""
    page.route("**/cdn.jsdelivr.net/**", lambda route: route.abort())
    open_overview(page)
    expect(page.get_by_text("Chart library unavailable").first).to_be_visible()
    expect(page.get_by_test_id("tile-system")).to_be_visible()


def test_data_load_failure_shows_error(page: Page):
    """A server error on the run index shows an error message instead of a blank page."""
    page.route("**/data/runs/index.json", lambda route: route.fulfill(status=500, body="boom"))
    page.goto("/index.html")
    expect(page.get_by_test_id("load-error")).to_contain_text("HTTP 500")


def test_run_without_live_tests_says_so(page: Page):
    """A run with only self-test results (before deployment) explains that no live tests ran
    instead of showing '- of 0 system tests'."""

    def self_test_only(route):
        index = route.fetch().json()
        for layer in ("api", "ui", "perf"):
            index[0]["layers"].pop(layer, None)
        route.fulfill(json=index)

    page.route("**/data/runs/index.json", self_test_only)
    open_overview(page)
    expect(page.get_by_test_id("no-live-tests")).to_contain_text("No live system tests")
    expect(page.get_by_test_id("latest-run")).not_to_contain_text("of 0 system tests")


def test_empty_history_shows_empty_state(page: Page):
    """With no runs published yet, the overview says so."""
    page.route("**/data/runs/index.json", lambda route: route.fulfill(json=[]))
    page.goto("/index.html")
    expect(page.get_by_text("No test runs have been published yet.")).to_be_visible()
