"""Shared setup for the Noisefloor demo tests: flaky and slow on purpose, off by default.

Noisefloor (a separate project) reads Jenkins build history to find flaky tests and runtime
regressions. These tests give it a known answer key, expected.json.

- Every test here is skipped unless NOISEFLOOR_DEMO=1. CrashCart's own CI never sets it, so
  its runs and dashboard are unaffected.
- Every "random" outcome is seeded from the build number (BUILD_NUMBER, set by Jenkins). The
  same build number always gives the same results, so history can be rebuilt exactly, while
  re-runs of the same commit (new build numbers) can disagree, which is what flakiness is.
- The demo tests' order is shuffled per build with the same seed, so the order-dependent test
  really meets different orders.
"""

import os
import random
from pathlib import Path

import pytest

DEMO_DIR = Path(__file__).parent


def demo_enabled() -> bool:
    return os.getenv("NOISEFLOOR_DEMO") == "1"


def build_seed() -> str:
    # NOISEFLOOR_DEMO_SEED lets a local run copy any build's outcomes; Jenkins sets BUILD_NUMBER.
    return os.getenv("NOISEFLOOR_DEMO_SEED") or os.getenv("BUILD_NUMBER") or "0"


def rng_for(name: str) -> random.Random:
    """A random stream for one test in one build. Seeding from a string is stable across
    processes (unlike hash()), and each test has its own stream, so adding a test never
    changes another test's outcomes."""
    return random.Random(f"{build_seed()}:{name}")


def _is_demo(item: pytest.Item) -> bool:
    return DEMO_DIR in Path(item.path).parents


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    positions = [index for index, item in enumerate(items) if _is_demo(item)]
    if not positions:
        return
    if not demo_enabled():
        skip = pytest.mark.skip(reason="Noisefloor demo test: runs only with NOISEFLOOR_DEMO=1")
        for index in positions:
            items[index].add_marker(skip)
        return
    # Shuffle only the demo tests, in place, leaving every other test where pytest put it.
    shuffled = [items[index] for index in positions]
    random.Random(f"{build_seed()}:order").shuffle(shuffled)
    for index, item in zip(positions, shuffled, strict=True):
        items[index] = item


@pytest.fixture
def demo_rng(request: pytest.FixtureRequest) -> random.Random:
    return rng_for(request.node.name)
