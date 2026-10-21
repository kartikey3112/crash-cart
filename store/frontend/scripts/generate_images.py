"""Generate the store's SVG artwork: one illustration per seeded product, plus the logo.

The product list is read from the backend seed (single source of truth), so the images
always match the catalog. All artwork is simple original geometry: no third-party assets.

Usage (from the repo root):  python store/frontend/scripts/generate_images.py
"""

import sys
from html import escape
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FRONTEND.parent / "backend"))

from app.seed import CATALOG, INACTIVE_PRODUCT  # noqa: E402

OUT_DIR = FRONTEND / "public" / "img"
ACCENT = "#e4572e"

# (background, darker shade) per category
PALETTES = {
    "audio": ("#fde8e1", "#c2410c"),
    "wearables": ("#e0f2fe", "#0369a1"),
    "smart-home": ("#dcfce7", "#15803d"),
    "computer-accessories": ("#ede9fe", "#6d28d9"),
    "phone-accessories": ("#fef9c3", "#a16207"),
    "gaming": ("#fce7f3", "#be185d"),
}

# Simple line icons drawn around the centre (200, 120) of a 400x300 canvas.
ICONS = {
    "audio": (
        '<path d="M140 150 v-30 a60 60 0 0 1 120 0 v30" fill="none" stroke-width="14"/>'
        '<rect x="122" y="140" width="36" height="56" rx="10"/>'
        '<rect x="242" y="140" width="36" height="56" rx="10"/>'
    ),
    "wearables": (
        '<rect x="176" y="40" width="48" height="40" rx="6"/>'
        '<rect x="176" y="160" width="48" height="40" rx="6"/>'
        '<rect x="160" y="78" width="80" height="84" rx="18"/>'
        '<circle cx="200" cy="120" r="22" fill="#fff"/>'
    ),
    "smart-home": (
        '<path d="M130 125 L200 65 L270 125 Z"/>'
        '<rect x="145" y="120" width="110" height="80"/>'
        '<rect x="188" y="150" width="24" height="50" fill="#fff"/>'
    ),
    "computer-accessories": (
        '<rect x="120" y="60" width="160" height="100" rx="8"/>'
        '<rect x="132" y="72" width="136" height="76" rx="4" fill="#fff"/>'
        '<rect x="190" y="160" width="20" height="26"/>'
        '<rect x="160" y="184" width="80" height="12" rx="6"/>'
    ),
    "phone-accessories": (
        '<rect x="160" y="45" width="80" height="150" rx="14"/>'
        '<rect x="170" y="62" width="60" height="105" rx="4" fill="#fff"/>'
        '<circle cx="200" cy="181" r="6" fill="#fff"/>'
    ),
    "gaming": (
        '<rect x="115" y="85" width="170" height="80" rx="40"/>'
        '<rect x="148" y="112" width="34" height="10" fill="#fff"/>'
        '<rect x="160" y="100" width="10" height="34" fill="#fff"/>'
        '<circle cx="238" cy="110" r="8" fill="#fff"/>'
        '<circle cx="256" cy="128" r="8" fill="#fff"/>'
    ),
}


def wrap(text: str, width: int = 24) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    return [*lines, current][:2]


def product_svg(sku: str, name: str, slug: str) -> str:
    background, shade = PALETTES[slug]
    text = "".join(
        f'<text x="200" y="{238 + i * 24}" text-anchor="middle">{escape(line)}</text>'
        for i, line in enumerate(wrap(name))
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" role="img" aria-label="{escape(name)}">
<rect width="400" height="300" fill="{background}"/>
<g fill="{shade}" stroke="{shade}">{ICONS[slug]}</g>
<g font-family="system-ui, sans-serif" font-size="19" font-weight="600" fill="#1f2430">{text}</g>
<text x="384" y="26" text-anchor="end" font-family="monospace" font-size="13" fill="{shade}">{sku}</text>
</svg>
"""


LOGO = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="CrashCart">
<rect width="64" height="64" rx="14" fill="{ACCENT}"/>
<path d="M12 18 h7 l6 24 h22 l5-16 H22" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="28" cy="49" r="3.5" fill="#fff"/>
<circle cx="44" cy="49" r="3.5" fill="#fff"/>
<path d="M38 8 l-5 9 h5 l-4 9" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def main() -> None:
    product_dir = OUT_DIR / "products"
    product_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for slug, _category, prefix, products in CATALOG:
        for number, (name, _price, _stock) in enumerate(products, start=1):
            sku = f"{prefix}-{number:03d}"
            (product_dir / f"{sku.lower()}.svg").write_text(
                product_svg(sku, name, slug), encoding="utf-8", newline="\n"
            )
            count += 1

    slug, sku, name, _price = INACTIVE_PRODUCT
    (product_dir / f"{sku.lower()}.svg").write_text(
        product_svg(sku, name, slug), encoding="utf-8", newline="\n"
    )
    (product_dir / "placeholder.svg").write_text(
        product_svg("NEW", "CrashCart product", "gaming"), encoding="utf-8", newline="\n"
    )
    for filename in ("logo.svg", "favicon.svg"):
        (OUT_DIR / filename).write_text(LOGO, encoding="utf-8", newline="\n")
    print(f"Wrote {count + 2} product images and the logo to {OUT_DIR}")


if __name__ == "__main__":
    main()
