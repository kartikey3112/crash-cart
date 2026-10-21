"""Builds the fixed site the dashboard tests run against, using the real pipeline and its
sample inputs: two runs of the same sample data, the second with cart_rounding switched on."""

import os
import shutil
from pathlib import Path

from pipeline import build
from pipeline.assemble import assemble

SAMPLES = Path(__file__).resolve().parents[2] / "pipeline" / "tests" / "samples" / "raw"
CLEAN_RUN = "run-clean"
BUG_RUN = "run-bugs"
RUNS = (
    (CLEAN_RUN, "2026-10-20T10:00:00+00:00", ""),
    (BUG_RUN, "2026-10-21T10:00:00+00:00", "cart_rounding"),
)


def build_site(site: Path) -> None:
    previous = os.environ.get("ALLURE_CMD")
    os.environ["ALLURE_CMD"] = str(site / "no-allure")  # skip the slow Allure step
    try:
        for run_id, timestamp, bugs in RUNS:
            raw = site.parent / f"raw-{run_id}"
            shutil.copytree(SAMPLES, raw)
            build.build(
                build.parse_args(
                    [
                        "--raw",
                        str(raw),
                        "--site",
                        str(site),
                        "--run-id",
                        run_id,
                        "--sha",
                        "0123456789abcdef0123456789abcdef01234567",
                        "--timestamp",
                        timestamp,
                        "--trigger",
                        "push",
                        "--bugs",
                        bugs,
                    ]
                )  # fmt: skip
            )
    finally:
        if previous is None:
            os.environ.pop("ALLURE_CMD")
        else:
            os.environ["ALLURE_CMD"] = previous
    assemble(site)
