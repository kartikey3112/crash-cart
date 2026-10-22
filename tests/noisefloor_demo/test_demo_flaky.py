"""Flaky on purpose. Each test fails in a known share of builds, for a realistic reason.

The causes are real (a fixed sleep racing a background job, state leaking between tests, an
edge case only some random inputs hit, a timeout, a time-zone slip). Only the dice are seeded
(see conftest.py), so a given build number always gives the same outcome. The designed failure
rates are listed in expected.json.
"""

import threading
import time
from datetime import UTC, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

pytestmark = [pytest.mark.demo, pytest.mark.feature("noisefloor-demo")]

STORE_TZ = timezone(timedelta(hours=5, minutes=30))  # the store's local time (IST)


# --- 1. Timing race: a fixed sleep instead of waiting for the job (fails 20% of builds) ---


def test_demo_background_export_finishes_before_check(demo_rng):
    """The export job is checked after a fixed 50 ms sleep, so a slow job is caught unfinished."""
    job_ms = 90 if demo_rng.random() < 0.20 else 10
    done = threading.Event()
    threading.Timer(job_ms / 1000, done.set).start()
    time.sleep(0.05)  # the bug: should be done.wait(timeout=...)
    assert done.is_set(), f"export still running after 50 ms (this build's job took {job_ms} ms)"


# --- 2. Order dependence: module state leaks between tests (fails when the order is wrong) ---

_saved_carts: list[str] = []  # module-level cache that nothing ever clears: the root cause


def test_demo_saving_a_cart_keeps_it_for_later():
    """Saving a cart stores its items in the shared saved-carts cache."""
    _saved_carts.append("PHN-003")
    assert "PHN-003" in _saved_carts


def test_demo_new_session_has_no_saved_carts():
    """A new session sees no saved carts; fails whenever the saving test ran first."""
    assert _saved_carts == [], f"items leaked from an earlier test: {_saved_carts}"


# --- 3. Random data: an off-by-one only some quantities hit (fails 15% of builds) ---


def bulk_discount_percent(quantity: int) -> int:
    """Demo code under test. The rule is 5% from 10 items, 10% from 15 and 15% at 20,
    but the comparisons use > instead of >=."""
    if quantity > 20:
        return 15
    if quantity > 15:
        return 10
    if quantity > 10:
        return 5
    return 0


def test_demo_bulk_discount_for_random_quantity(demo_rng):
    """A randomly chosen quantity from 1 to 20 gets the bulk discount of its tier."""
    quantity = demo_rng.randint(1, 20)
    expected = 15 if quantity >= 20 else 10 if quantity >= 15 else 5 if quantity >= 10 else 0
    assert bulk_discount_percent(quantity) == expected, f"wrong discount for {quantity} items"


# --- 4. Slow dependency: a short client timeout (fails 10% of builds) ---


@pytest.fixture
def price_service(demo_rng):
    """A local stand-in for a pricing service that is sometimes slow to answer."""
    delay_s = 0.30 if demo_rng.random() < 0.10 else 0.01

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(delay_s)
            body = b'{"price_cents": 999}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep test output clean
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # port 0: any free port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_demo_price_service_answers_within_timeout(price_service):
    """The price lookup uses a 150 ms timeout, which a slow answer from the service exceeds."""
    response = httpx.get(f"{price_service}/price/PHN-003", timeout=0.15)
    assert response.json() == {"price_cents": 999}


# --- 5. Time zones: the order date uses UTC, not store time (fails about 23% of builds) ---


def order_date_label(placed_at: datetime) -> str:
    """Demo code under test: should show the date in the store's time zone, but uses UTC."""
    return placed_at.astimezone(UTC).date().isoformat()


def test_demo_order_date_uses_store_time_zone(demo_rng):
    """An order placed at a random minute of the day shows the store's local date."""
    minute_of_day = demo_rng.randrange(24 * 60)  # UTC; from 18:30 UTC it's already tomorrow in IST
    placed_at = datetime(2026, 6, 1, tzinfo=UTC) + timedelta(minutes=minute_of_day)
    expected = placed_at.astimezone(STORE_TZ).date().isoformat()
    assert order_date_label(placed_at) == expected, f"wrong date for {placed_at:%H:%M} UTC"


# --- 6. Random data: names are cut to the wrong length (fails 30% of builds) ---


def shipping_label_name(full_name: str) -> str:
    """Demo code under test: labels fit 30 characters, but the code cuts at 21."""
    return full_name[:21]


def test_demo_shipping_label_keeps_full_name(demo_rng):
    """A random name of 1 to 30 characters fits on the label unchanged."""
    length = demo_rng.randint(1, 30)
    name = "".join(demo_rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(length))
    assert shipping_label_name(name) == name, f"a {length}-character name was cut"
