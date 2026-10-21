"""Decide what a CI run does, from the trigger and the manual-run inputs.

Automatic runs (push, schedule) run every live suite on Chromium with no bug switches.
Manual runs use the workflow_dispatch inputs, validated here so a typo fails the run
immediately instead of silently testing less. If the live URLs aren't configured yet
(before deployment), live testing is skipped and only the self-test results are published.

Usage in CI (writes key=value lines to $GITHUB_OUTPUT):
  python -m pipeline.ci_plan --event push --has-urls true [--suites ..] [--browsers ..] [--bugs ..]
"""

import argparse
import json
import os
import sys

from tests.config import KNOWN_BUGS

SUITES = ("api", "ui", "perf")
BROWSERS = ("chromium", "firefox", "webkit")


class PlanError(ValueError):
    pass


def split(text: str) -> list[str]:
    return [item.strip().lower() for item in (text or "").split(",") if item.strip()]


def plan(event: str, has_urls: bool, suites: str = "", browsers: str = "", bugs: str = "") -> dict:
    manual = event == "workflow_dispatch"
    chosen_suites = split(suites) if manual else list(SUITES)
    chosen_browsers = split(browsers) if manual else ["chromium"]
    chosen_bugs = split(bugs) if manual else []

    for label, values, allowed in (
        ("suite", chosen_suites, SUITES),
        ("browser", chosen_browsers, BROWSERS),
        ("bug switch", chosen_bugs, KNOWN_BUGS),
    ):
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            raise PlanError(f"unknown {label}(s): {unknown}; allowed: {list(allowed)}")
    if "ui" in chosen_suites and not chosen_browsers:
        raise PlanError("the ui suite needs at least one browser")

    live = has_urls and bool(chosen_suites)
    return {
        "live": live,
        "run_api": live and "api" in chosen_suites,
        "run_ui": live and "ui" in chosen_suites,
        "run_perf": live and "perf" in chosen_suites,
        # Fixed order, never empty: an empty list would make an invalid browser matrix even
        # when the UI job is skipped.
        "browsers": [b for b in BROWSERS if b in chosen_browsers] or ["chromium"],
        "bugs": ",".join(b for b in KNOWN_BUGS if b in chosen_bugs),
        "reason": "" if live else ("live URLs not configured" if not has_urls else "no suites"),
    }


def to_outputs(result: dict) -> str:
    """GitHub Actions output lines; booleans as true/false, browsers as a JSON array."""
    lines = []
    for key, value in result.items():
        if isinstance(value, bool):
            value = str(value).lower()
        elif isinstance(value, list):
            value = json.dumps(value)
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True)
    parser.add_argument("--has-urls", default="false")
    parser.add_argument("--suites", default="")
    parser.add_argument("--browsers", default="")
    parser.add_argument("--bugs", default="")
    args = parser.parse_args(argv)
    try:
        result = plan(args.event, args.has_urls == "true", args.suites, args.browsers, args.bugs)
    except PlanError as exc:
        print(f"::error::Invalid run inputs: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    if output := os.getenv("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(to_outputs(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
