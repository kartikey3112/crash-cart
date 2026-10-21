"""Read JUnit XML into per-test results, folding retries into one result per test.

pytest-rerunfailures writes EVERY attempt as its own <testcase> in order:
  - an attempt that will be retried has no <failure> child (but keeps its properties),
  - the final attempt carries <failure>/<error>/<skipped> if it didn't pass.
So: final status = last attempt; a test with more than one attempt whose last attempt
passed is "flaky" (it failed, then passed on retry).
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ARTIFACT_PROPERTIES = {"playwright_trace": "trace", "playwright_screenshot": "screenshot"}


@dataclass
class Attempt:
    test_id: str
    name: str
    status: str  # passed | failed | error | skipped
    duration_s: float
    message: str = ""
    artifacts: list[dict] = field(default_factory=list)  # [{"type", "path"}]


@dataclass
class TestResult:
    __test__ = False  # not a pytest test class, despite the name

    test_id: str
    name: str
    status: str  # passed | failed | error | skipped | flaky
    duration_s: float
    attempts: int
    message: str
    artifacts: list[dict]


def node_id(classname: str, name: str, id_prefix: str = "") -> str:
    """'tests.api.test_cart' + 'test_x[p]' -> 'tests/api/test_cart.py::test_x[p]'."""
    return f"{id_prefix}{classname.replace('.', '/')}.py::{name}"


def artifact_path(value: str) -> str:
    """Normalise a Playwright artifact path to start at 'test-results/'. JUnit may hold an
    absolute path, a relative one, or a CI runner's path, depending on where pytest ran."""
    path = value.replace("\\", "/")
    marker = path.find("test-results/")
    return path[marker:] if marker >= 0 else path


def first_line(text: str | None, limit: int = 300) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:limit]
    return ""


def parse_attempts(path: Path, id_prefix: str = "") -> list[Attempt]:
    attempts = []
    for case in ET.parse(path).getroot().iter("testcase"):
        status, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            child = case.find(tag)
            if child is not None:
                status = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = first_line(child.get("message") or child.text)
                break
        artifacts = [
            {
                "type": ARTIFACT_PROPERTIES[p.get("name")],
                "path": artifact_path(p.get("value", "")),
            }
            for p in case.iter("property")
            if p.get("name") in ARTIFACT_PROPERTIES
        ]
        attempts.append(
            Attempt(
                test_id=node_id(case.get("classname", ""), case.get("name", ""), id_prefix),
                name=case.get("name", ""),
                status=status,
                duration_s=float(case.get("time") or 0),
                message=message,
                artifacts=artifacts,
            )
        )
    return attempts


def fold_retries(attempts: list[Attempt]) -> list[TestResult]:
    """Group attempts by test id (keeping first-seen order) into one result each."""
    grouped: dict[str, list[Attempt]] = {}
    for attempt in attempts:
        grouped.setdefault(attempt.test_id, []).append(attempt)

    results = []
    for test_id, runs in grouped.items():
        final = runs[-1]
        status = final.status
        if status == "passed" and len(runs) > 1:
            status = "flaky"
        # Keep the most useful message: the final failure, or the first attempt's for flaky.
        message = final.message or next((r.message for r in runs if r.message), "")
        results.append(
            TestResult(
                test_id=test_id,
                name=final.name,
                status=status,
                duration_s=round(sum(r.duration_s for r in runs), 3),
                attempts=len(runs),
                message=message,
                artifacts=[a for r in runs for a in r.artifacts],
            )
        )
    return results


def suite_seconds(path: Path) -> float:
    """Wall time recorded by pytest for the whole file (sum over <testsuite> elements)."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    return round(sum(float(s.get("time") or 0) for s in suites), 2)
