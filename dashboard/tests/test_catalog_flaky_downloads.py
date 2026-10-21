import pytest
from playwright.sync_api import Page, expect

from dashboard.tests.fixture_site import CLEAN_RUN


def test_catalog_separates_system_and_unit_tests(page: Page):
    """The catalog lists 6 system tests and, on its own tab, 1 backend unit test."""
    page.goto("/catalog.html")
    expect(page.get_by_test_id("catalog-count")).to_have_text("6 of 6 tests")
    page.get_by_test_id("catalog-tab-unit").click()
    expect(page.get_by_test_id("catalog-count")).to_have_text("1 of 1 tests")
    expect(page.get_by_test_id("catalog-row")).to_contain_text("Fractional cents round half-up.")


def test_catalog_search_matches_docstrings(page: Page):
    """Searching by what a test checks (its docstring) finds it."""
    page.goto("/catalog.html")
    page.get_by_test_id("catalog-search").fill("pricing rules")
    expect(page.get_by_test_id("catalog-row")).to_have_count(1)
    expect(page.get_by_test_id("catalog-row")).to_contain_text("test_totals[one-cable]")


def test_catalog_bug_filter_and_coverage_table(page: Page):
    """Filtering by a bug switch shows its tests, and the coverage table counts them by layer."""
    page.goto("/catalog.html")
    page.get_by_test_id("catalog-bug").select_option("sort_desc_broken")
    expect(page.get_by_test_id("catalog-row")).to_have_count(1)
    coverage = page.get_by_test_id("bug-coverage").locator("tbody tr")
    expect(coverage).to_have_count(2)
    expect(coverage.filter(has_text="cart_rounding")).to_contain_text("1")


def test_flaky_page_lists_retry_flaky_test(page: Page):
    """The test that passed only on retry is listed, linking to the run it happened in."""
    page.goto("/flaky.html")
    row = page.get_by_test_id("flaky-row")
    expect(row).to_have_count(1)
    expect(row).to_contain_text("test_badge[chromium]")
    expect(row.get_by_role("link", name=CLEAN_RUN)).to_be_visible()
    expect(page.get_by_test_id("flaky-page")).to_contain_text("1 run with bug switches excluded")


def test_flaky_page_empty_state(page: Page):
    """With no flaky tests, the page says so instead of showing an empty table."""
    empty = {"generated_at": None, "window_days": 30, "runs_considered": 4,
             "runs_excluded_with_bugs": 0, "tests": []}  # fmt: skip
    page.route("**/data/flaky.json", lambda route: route.fulfill(json=empty))
    page.goto("/flaky.html")
    expect(page.get_by_test_id("flaky-empty")).to_contain_text("No flaky tests detected.")


def test_downloads_are_real_files(page: Page, base_url: str):
    """Every download link returns the file: the PDF is a PDF and the JUnit zip is a zip."""
    page.goto("/downloads.html")
    expect(page.get_by_test_id("download-row")).to_have_count(2)
    links = page.get_by_test_id("download-link")
    expect(links).to_have_count(4)  # JUnit + PDF per run (no Allure CLI in this fixture)
    for link in links.all():
        body = page.request.get(f"{base_url}/{link.get_attribute('href')}").body()
        assert body[:4] in (b"%PDF", b"PK\x03\x04"), link.get_attribute("href")


@pytest.mark.parametrize(
    "path", ["index.html", "runs.html", "catalog.html", "flaky.html", "downloads.html"]
)
def test_navigation_marks_current_page(page: Page, path: str):
    """Each page has exactly one h1 and highlights itself in the navigation."""
    page.goto(f"/{path}")
    expect(page.locator("main h1")).to_have_count(1)
    current = page.locator('nav a[aria-current="page"]')
    expect(current).to_have_count(1)
    expect(current).to_have_attribute("href", path)


@pytest.mark.parametrize(
    "path", ["index.html", "runs.html", "catalog.html", f"run.html?id={CLEAN_RUN}"]
)
def test_no_horizontal_scroll_on_phones(page: Page, path: str):
    """At a 400px phone width the page never scrolls sideways (tables scroll in their box)."""
    page.set_viewport_size({"width": 400, "height": 800})
    page.goto(f"/{path}")
    expect(page.locator("main h1")).to_be_visible()
    assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth")


def test_dark_mode_follows_system_setting(page: Page):
    """With a dark system theme, the page background switches to the dark palette."""
    page.emulate_media(color_scheme="dark")
    page.goto("/index.html")
    expect(page.get_by_test_id("latest-run")).to_be_visible()
    assert (
        page.evaluate("getComputedStyle(document.body.parentElement).backgroundColor")
        == "rgb(13, 13, 13)"
    )
