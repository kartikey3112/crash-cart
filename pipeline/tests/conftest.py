import shutil
from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent / "samples"


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    """A private copy of the sample raw inputs (tests may modify it)."""
    target = tmp_path / "raw"
    shutil.copytree(SAMPLES / "raw", target)
    return target


@pytest.fixture
def site(tmp_path: Path) -> Path:
    return tmp_path / "site"


@pytest.fixture(autouse=True)
def no_allure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point ALLURE_CMD at nothing so tests never depend on a local Allure install;
    the one test that wants Allure overrides this."""
    monkeypatch.setenv("ALLURE_CMD", str(tmp_path / "no-allure-here"))
