"""Fixtures for the dashboard's own Playwright tests.

The dashboard is tested against a small, fixed site built by the real pipeline from its
sample inputs (see fixture_site.py). Every number on screen is known in advance, no backend
is needed, and CI can run this suite before publishing.
"""

import functools
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from dashboard.tests.fixture_site import build_site


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # keep test output readable
        pass


@pytest.fixture(scope="session")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    site = tmp_path_factory.mktemp("dashboard") / "site"
    build_site(site)
    return site


@pytest.fixture(scope="session")
def base_url(site: Path) -> Iterator[str]:
    """Serve the built site on a free local port for the whole session (overrides
    pytest-base-url, so page.goto("/runs.html") works)."""
    handler = functools.partial(QuietHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def console_errors(page) -> list[str]:
    """Collects console errors and uncaught exceptions for tests that expect none."""
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    return errors
