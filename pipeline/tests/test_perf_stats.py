"""Checks for the perf runner's statistics (tests/perf/jmeter_runner.py), which produce the
p95 numbers this pipeline publishes."""

import pytest

from tests.perf.jmeter_runner import nearest_rank, parse_jtl

JTL_HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success\n"


@pytest.mark.parametrize(
    ("percentile", "expected"), [(50, 50), (95, 95), (99, 99), (100, 100), (1, 1)]
)
def test_nearest_rank_on_1_to_100(percentile, expected):
    """On the values 1..100, the Pth percentile (nearest rank) is exactly P."""
    assert nearest_rank(list(range(1, 101)), percentile) == expected


def test_nearest_rank_small_sample():
    """With 3 samples, p95 is the largest (rank = ceil(0.95 * 3) = 3)."""
    assert nearest_rank([10, 20, 30], 95) == 30


def test_parse_jtl_counts_errors_and_throughput(tmp_path):
    """Errors come from the success column; throughput = samples / time window."""
    rows = [
        "1000,100,s,200,OK,t,text,true",
        "1500,300,s,200,OK,t,text,true",
        "2000,200,s,500,ERR,t,text,false",
        "2800,200,s,200,OK,t,text,true",  # window: 1000 -> 3000 ms = 2 s
    ]
    jtl = tmp_path / "r.jtl"
    jtl.write_text(JTL_HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    stats = parse_jtl(jtl)
    assert (stats.samples, stats.errors, stats.error_rate) == (4, 1, 0.25)
    assert (stats.p50_ms, stats.p95_ms, stats.max_ms) == (200, 300, 300)
    assert stats.throughput_rps == 2.0


def test_parse_jtl_rejects_empty_results(tmp_path):
    """A results file with no samples is an error, not a silent pass."""
    jtl = tmp_path / "empty.jtl"
    jtl.write_text(JTL_HEADER, encoding="utf-8")
    with pytest.raises(ValueError, match="no samples"):
        parse_jtl(jtl)
