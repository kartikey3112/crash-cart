import pytest
from sqlalchemy import select

from app.db import make_engine, make_session_factory
from app.export_openapi import SPEC_PATH, render_spec
from app.models import Category, Coupon, Product
from app.seed import reset_database

pytestmark = pytest.mark.unit


def _snapshot(settings) -> list[tuple]:
    engine = make_engine("sqlite://")
    factory = make_session_factory(engine)
    reset_database(engine, factory, settings)
    with factory() as session:
        rows = [
            (p.id, p.sku, p.name, p.price_cents, p.stock, p.is_active, p.created_at)
            for p in session.scalars(select(Product).order_by(Product.id))
        ]
        rows += [(c.id, c.slug) for c in session.scalars(select(Category).order_by(Category.id))]
        rows += [(c.code, c.value, c.expires_at) for c in session.scalars(select(Coupon))]
    engine.dispose()
    return rows


@pytest.mark.feature("seed")
def test_seed_is_deterministic(settings):
    """Two independent seeds produce identical products, categories and coupons."""
    assert _snapshot(settings) == _snapshot(settings)


@pytest.mark.feature("api-contract")
def test_committed_openapi_spec_is_current():
    """openapi.json in the repo matches the running code (run `python -m app.export_openapi`)."""
    assert SPEC_PATH.read_text(encoding="utf-8") == render_spec()
