"""Copy the static dashboard (HTML/CSS/JS) into the site folder next to data/ and reports/,
producing the exact folder that gets published to GitHub Pages.

Usage:  python -m pipeline.assemble --site site
"""

import argparse
import shutil
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard"


def assemble(site: Path) -> int:
    """Copy every dashboard file into site/, overwriting older copies. Returns files copied."""
    copied = 0
    for source in DASHBOARD.rglob("*"):
        if source.is_file() and source.suffix != ".md":  # docs stay in the repo, not on the site
            target = site / source.relative_to(DASHBOARD)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
    # GitHub Pages runs Jekyll by default, which hides folders starting with "_".
    (site / ".nojekyll").touch()
    return copied


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True)
    print(f"Copied {assemble(Path(parser.parse_args().site))} dashboard files")
