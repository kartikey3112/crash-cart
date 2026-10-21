"""Rebuild data/runs/index.json (and flaky.json) from the per-run files.

Run this after changing what a run summary contains, so older runs get the new fields.
Usage:  python -m pipeline.reindex --site site
"""

import argparse
from pathlib import Path

from pipeline.history import compute_flaky, rebuild_index

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True)
    site = Path(parser.parse_args().site)
    index = rebuild_index(site)
    compute_flaky(site)
    print(f"Re-indexed {len(index)} runs")
