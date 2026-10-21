# CrashCart results dashboard

A static site made of plain HTML, CSS and ES-module JavaScript, with no build step. It reads
the JSON files the pipeline writes (`data/`) and links to the per-run downloads (`reports/`).
It's published to GitHub Pages by CI.

| Page | What it shows |
|---|---|
| `index.html` Overview | Latest run, pass-rate and duration trends, perf, coverage, which injected bugs were caught |
| `runs.html` Run history | Every run, filterable by bug switches, trigger and result |
| `run.html?id=` Run detail | Failures first (message, trace, screenshot, Trace Viewer link), per-layer tabs, perf table, and a separate backend unit-test section |
| `catalog.html` Test catalog | Every test with its docstring, layer, feature, targeted bug switch and latest result. Unit tests have their own tab. |
| `flaky.html` Flaky tests | Same-commit conflicts, pass-on-retry and 30-day flip rate (runs with bug switches excluded) |
| `downloads.html` Downloads | Allure report zip, JUnit zip and PDF summary for the newest 30 runs |

## Run locally

```powershell
python -m pipeline.local_run           # produces site/ with data, reports and these files
python -m http.server 8080 -d site     # then open http://localhost:8080
```

The pages need a web server, because ES modules and `fetch` don't work from `file://`.
`python -m pipeline.assemble --site site` re-copies just the dashboard files after edits.

## Tests

`dashboard/tests/` holds a Playwright suite for the dashboard itself:

```powershell
pytest dashboard/tests                  # Chromium; add --browser firefox / webkit
```

- **Fixed data.** It runs against a site built by the real pipeline from
  `pipeline/tests/samples`: two runs, the second with `cart_rounding` switched on. Every
  expected number is therefore known in advance, and no store backend is needed.
- **Served locally.** The site is served on a random local port for the session, so the
  suite can gate publishing in CI.
- **Network interception** covers the states you can't reach with real data:
  - the run index returning HTTP 500 or an empty list
  - the Chart.js CDN being blocked (the data must still render)
  - an empty flaky list
  - test names and messages containing `<script>`/`<img onerror>`, to prove they're shown
    as text and never executed
- **Also checked:** filters, tabs, search, Trace Viewer links per attempt, every download
  being a real PDF or zip, one `h1` and a highlighted nav item per page, no sideways
  scrolling at 400 px, and dark mode.
- **Not published.** `pipeline/assemble.py` only copies web assets (`.html .css .js .svg`
  and similar), outside `tests/`, so these files are never published.

## Design choices

- **Text goes in as text.** Pages build the DOM with a tiny `el()` helper that only ever sets
  text, never `innerHTML`, so test names or error messages can't inject markup.
- **Charts.** Chart.js 4.5.1 comes from jsDelivr, pinned with a subresource-integrity hash.
  - The colours are categorical slots 1–4 of a validated palette. They were checked with a
    palette validator for colour-blind separation in both light and dark mode, where they
    pass.
  - Two light-mode colours are under 3:1 contrast against the background, so every chart has
    an HTML legend and a "Show as table" view.
  - There is one y-axis per chart.
- **Runs with bug switches** are drawn as separate markers on the pass-rate chart and left
  out of flaky analysis, because their failures are deliberate.
- **Unit tests are kept apart** from the system tests: separate tiles, a separate run-detail
  section and a separate catalog tab.
- **Light and dark** both follow the visitor's system setting through CSS custom properties.
- **`data-testid` attributes** are on the main regions, so the dashboard itself can be
  tested.
