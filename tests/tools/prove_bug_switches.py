"""Prove that the suite catches every injected bug.

1. Collect the suite's catalog (which tests target which bug switch).
2. Baseline run with no bugs: every test must pass.
3. For each bug switch: run the suite with only that switch on (ENABLE_BUGS) and compare the
   failed tests with the tests tagged @pytest.mark.bug("<switch>").

A switch counts as CAUGHT when at least one test targeting it fails. Targeted tests that
still passed, and untargeted tests that failed ("collateral"), are reported too.

Usage:
    python -m tests.tools.prove_bug_switches --suite tests/api [--bugs a,b] [--workers 4]
Exit code 0 only if the baseline is green and every targeted switch was caught.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from tests.config import KNOWN_BUGS


def run_pytest(
    suite: str, junit: Path, workers: int, extra_env: dict, extra_args: list[str]
) -> float:
    cmd = [sys.executable, "-m", "pytest", suite, "-q", "--no-header", f"--junitxml={junit}"]
    if workers > 1:
        cmd += ["-n", str(workers)]
    started = time.monotonic()
    subprocess.run(
        cmd + extra_args, env={**os.environ, **extra_env}, capture_output=True, text=True
    )
    return time.monotonic() - started


def failed_tests(junit: Path) -> set[str]:
    """Node ids of tests that failed or errored, rebuilt from JUnit classname + name."""
    failed = set()
    for case in ET.parse(junit).getroot().iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            module = case.get("classname", "").replace(".", "/")
            failed.add(f"{module}.py::{case.get('name')}")
    return failed


def collect_catalog(suite: str, out: Path) -> list[dict]:
    cmd = [sys.executable, "-m", "pytest", suite, "--collect-only", "-q", f"--catalog-out={out}"]
    subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", default="tests/api")
    parser.add_argument("--bugs", default=",".join(KNOWN_BUGS))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default=None, help="write the JSON summary here")
    parser.add_argument("pytest_args", nargs="*", help="extra args passed to pytest (after --)")
    args = parser.parse_args()
    bugs = [b.strip() for b in args.bugs.split(",") if b.strip()]

    work = Path(tempfile.mkdtemp(prefix="bug-proof-"))
    catalog = collect_catalog(args.suite, work / "catalog.json")
    targets = {bug: {t["id"] for t in catalog if bug in t["bugs"]} for bug in bugs}
    print(f"Suite {args.suite}: {len(catalog)} tests collected\n")

    seconds = run_pytest(args.suite, work / "baseline.xml", args.workers, {}, args.pytest_args)
    baseline_failures = failed_tests(work / "baseline.xml")
    print(f"Baseline (no bugs): {len(baseline_failures)} failed in {seconds:.1f}s")
    if baseline_failures:
        print("  Baseline must be green before bugs can be judged:")
        for test_id in sorted(baseline_failures):
            print(f"    {test_id}")
        return 2

    results, all_caught = [], True
    print(
        "\n| Bug switch | Targeted tests | Targeted that failed | Collateral failures | Verdict |"
    )
    print("|---|---|---|---|---|")
    for bug in bugs:
        junit = work / f"{bug}.xml"
        seconds = run_pytest(
            args.suite, junit, args.workers, {"ENABLE_BUGS": bug}, args.pytest_args
        )
        failed = failed_tests(junit)
        targeted = targets[bug]
        caught = targeted & failed
        if not targeted:
            verdict = "not targeted in this suite"
        elif caught:
            verdict = "CAUGHT"
        else:
            verdict = "MISSED"
            all_caught = False
        results.append(
            {
                "bug": bug,
                "targeted": sorted(targeted),
                "caught_by": sorted(caught),
                "targeted_but_passed": sorted(targeted - failed),
                "collateral": sorted(failed - targeted),
                "verdict": verdict,
                "seconds": round(seconds, 1),
            }
        )
        print(
            f"| `{bug}` | {len(targeted)} | {len(caught)} | {len(failed - targeted)} | {verdict} |"
        )

    print("\nDetails:")
    for r in results:
        print(f"- {r['bug']} ({r['verdict']}, {r['seconds']}s)")
        for test_id in r["caught_by"]:
            print(f"    failed as intended: {test_id}")
        for test_id in r["targeted_but_passed"]:
            print(f"    targeted but PASSED: {test_id}")
        for test_id in r["collateral"]:
            print(f"    collateral failure: {test_id}")

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if all_caught else 1


if __name__ == "__main__":
    sys.exit(main())
