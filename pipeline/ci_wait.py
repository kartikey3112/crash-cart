"""Prepare the deployed store for a CI run: wait until it's awake (and, after a push, until
each deployment runs the right commit), then reset it to the seed state once.

"The right commit" is per service, because this is a monorepo: Render only redeploys the
backend when files under store/backend change. A deployment counts as current if it runs
the latest commit that touched its folder, or any newer commit up to HEAD.

Standard library + git only, so the CI job needs no installs (it needs full git history).

Usage:
  python -m pipeline.ci_wait --api URL --ui URL --token TOKEN [--wait-for-deploy]
                             [--wake-timeout 300] [--deploy-timeout 900]
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

BACKEND_DIR = "store/backend"
FRONTEND_DIR = "store/frontend"


def get_json(url: str, timeout: float = 15) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def git(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def acceptable_commits(path: str, cwd: str | None = None) -> list[str]:
    """The latest commit that changed `path`, plus every later commit on the way to HEAD.
    A deployment running any of these has the current code for that folder."""
    latest = git("log", "-1", "--format=%H", "--", path, cwd=cwd)
    if not latest:  # folder never changed: any commit in the history will do
        return git("rev-list", "HEAD", cwd=cwd).split()
    newer = git("rev-list", "--ancestry-path", f"{latest}..HEAD", cwd=cwd).split()
    return [latest, *newer]


def deploy_is_current(reported: str | None, acceptable: list[str]) -> bool:
    """Deploy platforms may report the full SHA or a prefix of it."""
    if not reported or reported in ("unknown", "dev"):
        return False
    return any(sha.startswith(reported) or reported.startswith(sha) for sha in acceptable)


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
    parser.add_argument("--wait-for-deploy", action="store_true")
    parser.add_argument("--wake-timeout", type=float, default=300)
    parser.add_argument("--deploy-timeout", type=float, default=900)
    args = parser.parse_args(argv)
    api, ui = args.api.rstrip("/"), args.ui.rstrip("/")

    def backend_awake() -> bool:
        return get_json(f"{api}/health")["status"] == "ok"

    try:
        waited = wait_until(backend_awake, args.wake_timeout, 5, "backend /health")
        print(f"Backend awake after {waited:.0f}s")
        if args.wait_for_deploy:
            for name, folder, url, key in (
                ("backend", BACKEND_DIR, f"{api}/health", "commit"),
                ("frontend", FRONTEND_DIR, f"{ui}/version.json", "commit"),
            ):
                acceptable = acceptable_commits(folder)
                print(f"{name}: needs {acceptable[0][:7]} (last change to {folder}) or newer")
                waited = wait_until(
                    lambda url=url, key=key, ok=acceptable: deploy_is_current(
                        get_json(url).get(key), ok
                    ),
                    args.deploy_timeout,
                    15,
                    f"{name} deploy",
                )
                print(f"{name} is current: {get_json(url).get(key)[:7]} (waited {waited:.0f}s)")
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
