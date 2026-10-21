"""Prepare the deployed store for a CI run: wait until it's awake (and, after a push, until
both deployments report the pushed commit), then reset it to the seed state once.

Standard library only, so the CI job needs no installs.

Usage:
  python -m pipeline.ci_wait --api URL --ui URL --token TOKEN [--expect-commit SHA]
                             [--wake-timeout 300] [--deploy-timeout 900]
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def get_json(url: str, timeout: float = 15) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def commit_matches(reported: str | None, expected: str) -> bool:
    """Deploy platforms may report the full SHA or a prefix of it."""
    return (
        bool(reported)
        and reported != "unknown"
        and (expected.startswith(reported) or reported.startswith(expected))
    )


def wait_until(
    check, timeout_s: float, interval_s: float, what: str, clock=time.monotonic, sleep=time.sleep
) -> float:
    """Call check() until it returns True; returns seconds waited or raises TimeoutError."""
    start = clock()
    last_error = "never checked"
    while clock() - start < timeout_s:
        try:
            if check():
                return clock() - start
            last_error = "not ready yet"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        sleep(interval_s)
    raise TimeoutError(f"{what} not ready after {timeout_s:.0f}s ({last_error})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True)
    parser.add_argument("--ui", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--expect-commit", default="")
    parser.add_argument("--wake-timeout", type=float, default=300)
    parser.add_argument("--deploy-timeout", type=float, default=900)
    args = parser.parse_args(argv)
    api, ui = args.api.rstrip("/"), args.ui.rstrip("/")
    sha = args.expect_commit

    def backend_awake() -> bool:
        return get_json(f"{api}/health")["status"] == "ok"

    def backend_current() -> bool:
        return commit_matches(get_json(f"{api}/health").get("commit"), sha)

    def frontend_current() -> bool:
        return commit_matches(get_json(f"{ui}/version.json").get("commit"), sha)

    try:
        waited = wait_until(backend_awake, args.wake_timeout, 5, "backend /health")
        print(f"Backend awake after {waited:.0f}s")
        if sha:
            label = sha[:7]
            waited = wait_until(backend_current, args.deploy_timeout, 15, f"backend {label}")
            print(f"Backend is running {label} (waited {waited:.0f}s)")
            waited = wait_until(frontend_current, args.deploy_timeout, 15, f"frontend {label}")
            print(f"Frontend is serving {label} (waited {waited:.0f}s)")
    except TimeoutError as exc:
        print(f"::error::{exc}")
        return 1

    request = urllib.request.Request(
        f"{api}/test/reset", method="POST", headers={"X-Test-Token": args.token}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            print(f"Store reset: {response.read().decode()}")
    except urllib.error.HTTPError as exc:
        print(f"::error::Reset failed with HTTP {exc.code} (is the TEST_TOKEN secret right?)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
