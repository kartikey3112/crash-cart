"""Tests that always pass but get slower at known commits on this branch.

Each test takes about 0.2 to 0.3 s to begin with. A later commit changes the code it calls
(workload.py) in a way that looks harmless, and from that commit on it takes about 1.2 s or
more. expected.json lists which commit slows down which test.
"""

import pytest

from tests.noisefloor_demo import workload

pytestmark = [pytest.mark.demo, pytest.mark.feature("noisefloor-demo")]


def test_demo_order_history_page(demo_rng):
    """The order history lists every order with its items."""
    orders = workload.load_order_history(demo_rng)
    assert len(orders) == workload.ORDER_COUNT and all(o["items"] == 2 for o in orders)


def test_demo_product_search_repeats(demo_rng):
    """Repeated searches for the same few terms return consistent counts."""
    terms = ["cable", "case", "earbuds", "speaker"] * 10
    assert workload.search_products(demo_rng, terms) == {t: len(t) for t in set(terms)}


def test_demo_tax_rates_for_regions(demo_rng):
    """Every shipping region gets the 8% tax rate."""
    regions = [f"region-{n}" for n in range(workload.TAX_LOOKUPS)]
    assert set(workload.tax_rates(demo_rng, regions).values()) == {8}


def test_demo_catalog_export_writes_every_row(demo_rng):
    """The catalog export writes every row exactly once."""
    assert workload.export_catalog(demo_rng) == workload.EXPORT_ROWS
