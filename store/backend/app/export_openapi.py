"""Write the OpenAPI spec to openapi.json.  Usage:  python -m app.export_openapi"""

import json
from pathlib import Path

from app.main import create_app

SPEC_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def render_spec() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SPEC_PATH.write_text(render_spec(), encoding="utf-8", newline="\n")
    print(f"Wrote {SPEC_PATH}")
