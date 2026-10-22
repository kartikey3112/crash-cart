"""Small stand-ins for store code, used only by the slow demo tests.

Each operation simulates the cost of database or service calls with time.sleep, so durations
are about the same on any machine. Later commits on this branch change some of these functions
in ways that look harmless but make them slower. expected.json names each of those commits.
"""

import random
import time

ORDER_COUNT = 100
SEARCH_CACHE_SIZE = 0  # no caching, so every search returns fresh results
TAX_LOOKUPS = 5
EXPORT_ROWS = 500
EXPORT_BATCH_SIZE = 100


def simulated_call(rng: random.Random, seconds: float) -> None:
    # +-10% jitter, so a test's duration varies a little between builds like real timings do.
    time.sleep(seconds * rng.uniform(0.9, 1.1))


def load_order_history(rng: random.Random) -> list[dict]:
    """Every order with its item count, loading each order's items on their own."""
    orders = []
    for order_id in range(ORDER_COUNT):
        simulated_call(rng, 0.012)  # one query per order
        orders.append({"order_id": order_id, "items": 2})
    return orders


def search_products(rng: random.Random, terms: list[str]) -> dict[str, int]:
    """Result counts per search term. Repeated terms are answered from a small cache."""
    cache: dict[str, int] = {}
    results = {}
    for term in terms:
        if term in cache:
            simulated_call(rng, 0.002)  # cache hit
        else:
            simulated_call(rng, 0.05)  # full search
            if len(cache) < SEARCH_CACHE_SIZE:
                cache[term] = len(term)
        results[term] = len(term)
    return results


RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = 0.25


def tax_service_call(rng: random.Random, region: str) -> int:
    simulated_call(rng, 0.04)
    return 8


def with_retries(call):
    """Run call(), retrying on connection errors with a fixed back-off."""
    for attempt in range(RETRY_ATTEMPTS):
        time.sleep(RETRY_BACKOFF_S)  # back off between attempts
        try:
            return call()
        except ConnectionError:
            if attempt == RETRY_ATTEMPTS - 1:
                raise


def tax_rates(rng: random.Random, regions: list[str]) -> dict[str, int]:
    """Tax rate in percent for each region, one service call each, retried on errors."""
    return {region: with_retries(lambda r=region: tax_service_call(rng, r)) for region in regions}


def export_catalog(rng: random.Random) -> int:
    """Write every catalog row to the export file in batches. Returns rows written."""
    written = 0
    while written < EXPORT_ROWS:
        batch = min(EXPORT_BATCH_SIZE, EXPORT_ROWS - written)
        simulated_call(rng, 0.002 + 0.0004 * batch)  # fixed cost per write, plus per row
        written += batch
    return written
