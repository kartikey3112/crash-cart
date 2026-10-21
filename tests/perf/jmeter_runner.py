"""Run the JMeter plan headless and turn its raw results (.jtl CSV) into statistics.

Percentiles are computed here, in plain Python, from every sample (nearest-rank method),
rather than read from a JMeter report, so the number that gates the build is easy to audit.
"""

import csv
import math
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

PLAN = Path(__file__).parent / "jmeter" / "endpoint_load.jmx"
DEFAULT_JMETER_HOME = Path.home() / "tools" / "apache-jmeter-5.6.3"


@dataclass(frozen=True)
class LoadProfile:
    threads: int
    rampup_s: int
    duration_s: int
    think_ms: int


@dataclass(frozen=True)
class PerfStats:
    samples: int
    errors: int
    error_rate: float  # 0.0 - 1.0
    p50_ms: int
    p95_ms: int
    p99_ms: int
    max_ms: int
    mean_ms: float
    throughput_rps: float

    def to_dict(self) -> dict:
        return asdict(self)


def find_jmeter() -> str:
    """JMETER_HOME, then the default install location, then `jmeter` on PATH."""
    script = "jmeter.bat" if platform.system() == "Windows" else "jmeter"
    for home in (os.getenv("JMETER_HOME"), DEFAULT_JMETER_HOME):
        if home and (Path(home) / "bin" / script).exists():
            return str(Path(home) / "bin" / script)
    on_path = shutil.which(script)
    if on_path:
        return on_path
    raise FileNotFoundError(
        f"JMeter not found. Set JMETER_HOME or install it to {DEFAULT_JMETER_HOME}."
    )


def nearest_rank(sorted_values: list[int], percentile: float) -> int:
    """The smallest value with at least `percentile`% of samples at or below it."""
    rank = math.ceil(percentile / 100 * len(sorted_values))
    return sorted_values[max(rank, 1) - 1]


def parse_jtl(jtl: Path) -> PerfStats:
    with jtl.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{jtl} has no samples: did JMeter reach the server?")
    elapsed = sorted(int(row["elapsed"]) for row in rows)
    errors = sum(1 for row in rows if row["success"].lower() != "true")
    first_start = min(int(row["timeStamp"]) for row in rows)
    last_end = max(int(row["timeStamp"]) + int(row["elapsed"]) for row in rows)
    window_s = max((last_end - first_start) / 1000, 0.001)
    return PerfStats(
        samples=len(rows),
        errors=errors,
        error_rate=errors / len(rows),
        p50_ms=nearest_rank(elapsed, 50),
        p95_ms=nearest_rank(elapsed, 95),
        p99_ms=nearest_rank(elapsed, 99),
        max_ms=elapsed[-1],
        mean_ms=round(sum(elapsed) / len(elapsed), 1),
        throughput_rps=round(len(rows) / window_s, 2),
    )


def run_jmeter(
    *,
    base_url: str,
    path: str,
    label: str,
    profile: LoadProfile,
    out_dir: Path,
    token: str = "",
    bug_switches: str = "",
    test_token: str = "",
) -> PerfStats:
    """Run one scenario. Writes <label>.properties, .jtl and .log into out_dir."""
    url = urlsplit(base_url)
    port = url.port or (443 if url.scheme == "https" else 80)
    out_dir.mkdir(parents=True, exist_ok=True)
    jtl, log = out_dir / f"{label}.jtl", out_dir / f"{label}.log"
    jtl.unlink(missing_ok=True)  # JMeter appends to an existing file

    properties = {
        "protocol": url.scheme,
        "host": url.hostname,
        "port": port,
        "path": path,
        "label": label,
        "threads": profile.threads,
        "rampup": profile.rampup_s,
        "duration": profile.duration_s,
        "think_ms": profile.think_ms,
        "token": token,
        "bug_switches": bug_switches,
        "test_token": test_token,
        "jmeter.save.saveservice.output_format": "csv",
    }
    # Properties go in a file (-q), not on the command line: on Windows jmeter.bat runs
    # through cmd.exe, which treats "&" in a URL query string as a command separator.
    props_file = out_dir / f"{label}.properties"
    props_file.write_text(
        "".join(f"{key}={value}\n" for key, value in properties.items()), encoding="utf-8"
    )
    cmd = [find_jmeter(), "-n", "-t", str(PLAN), "-q", str(props_file), "-l", str(jtl)]
    cmd += ["-j", str(log)]

    env = dict(os.environ)
    if java_home := os.getenv("JAVA_HOME"):
        # Make JMeter use the JDK in JAVA_HOME even if an older java is first on PATH.
        env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env["PATH"]
    result = subprocess.run(
        cmd, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=900
    )
    if result.returncode != 0 or not jtl.exists():
        raise RuntimeError(
            f"JMeter failed (exit {result.returncode}). See {log}\n{result.stdout[-1500:]}"
        )
    return parse_jtl(jtl)
