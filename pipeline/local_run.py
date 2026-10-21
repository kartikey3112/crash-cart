"""Run the suites locally the way CI does, then build the dashboard data.

Prerequisites: the backend on :8000 and the frontend preview on :4173 are already running
(see tests/README.md), JMeter and (optionally) Allure are installed.

Usage:
  python -m pipeline.local_run [--suites unit,api,ui,perf] [--bugs a,b]
                               [--perf-duration 20] [--site site] [--keep 30]
Suite failures don't stop the run: results are collected either way, like in CI.
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from pipeline import build
from pipeline.assemble import assemble

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(cmd: list[str], cwd: Path = REPO, env: dict | None = None) -> int:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suites", default="unit,api,ui,perf")
    parser.add_argument("--bugs", default="")
    parser.add_argument("--perf-duration", default="20", help="seconds per perf scenario")
    parser.add_argument("--browser", default="chromium", help="chromium, firefox or webkit")
    parser.add_argument("--raw", default="raw")
    parser.add_argument("--site", default="site")
    parser.add_argument("--keep", type=int, default=30)
    args = parser.parse_args()
    suites = set(args.suites.split(","))

    raw = (REPO / args.raw).resolve()
    shutil.rmtree(raw, ignore_errors=True)
    for sub in ("junit", "catalog", "perf", "allure-results"):
        (raw / sub).mkdir(parents=True)
    allure = f"--alluredir={raw / 'allure-results'}"
    env = {"ENABLE_BUGS": args.bugs, "PERF_RESULTS_DIR": str(raw / "perf")}

    # Catalogs always cover every test, whichever suites run.
    run([PY, "-m", "pytest", "tests", "--collect-only", "-q",
         f"--catalog-out={raw / 'catalog' / 'catalog-system.json'}"])  # fmt: skip
    backend = REPO / "store" / "backend"
    run([PY, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         f"--catalog-out={raw / 'catalog' / 'catalog-unit.json'}"], cwd=backend)  # fmt: skip

    if "unit" in suites:
        run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--cov=app", "--cov-branch",
             f"--cov-report=json:{raw / 'coverage.json'}", allure,
             f"--junitxml={raw / 'junit' / 'junit-unit.xml'}"], cwd=backend)  # fmt: skip
    if "api" in suites:
        run([PY, "-m", "pytest", "tests/api", "-q", "-n", "4", allure,
             f"--junitxml={raw / 'junit' / 'junit-api.xml'}"], env=env)  # fmt: skip
    if "ui" in suites:
        run([PY, "-m", "pytest", "tests/ui", "-q", "--reruns", "1", allure,
             "--browser", args.browser, f"--output={raw / 'test-results'}",
             f"--junitxml={raw / 'junit' / f'junit-ui-{args.browser}.xml'}"], env=env)  # fmt: skip
    if "perf" in suites:
        run([PY, "-m", "pytest", "tests/perf", "-q", allure,
             f"--junitxml={raw / 'junit' / 'junit-perf.xml'}"],
            env={**env, "PERF_DURATION_S": args.perf_duration})  # fmt: skip

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                         text=True).stdout.strip() or "unknown"  # fmt: skip
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=REPO, capture_output=True,
                            text=True).stdout.strip() or "local"  # fmt: skip
    now = datetime.now(UTC)
    build.build(
        build.parse_args(
            [
                "--raw",
                str(raw),
                "--site",
                str(REPO / args.site),
                "--run-id",
                f"local-{now:%Y%m%dT%H%M%S}",
                "--sha",
                sha,
                "--branch",
                branch,
                "--trigger",
                "local",
                "--timestamp",
                now.isoformat(timespec="seconds"),
                "--bugs",
                args.bugs,
                "--keep",
                str(args.keep),
            ]
        )  # fmt: skip
    )
    print(f"Assembled site: {assemble(REPO / args.site)} dashboard files copied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
