# Results pipeline

These scripts turn one run's raw test outputs into the static data the results dashboard
reads, plus the downloadable reports.

```
raw/ (one run)                    site/ (accumulates across runs)
  junit/*.xml          ─┐          data/runs/index.json      newest-first run summaries
  catalog/*.json        │          data/runs/<run_id>.json   every test result for one run
  perf/*.json           ├─ build ─▶ data/catalog.json         every test + docstring + markers
  allure-results/       │          data/flaky.json           flaky-test analysis
  coverage.json         │          reports/<run_id>/         allure-report.zip, junit.zip,
  test-results/ (UI)   ─┘                                    summary.pdf, artifacts/
```

## Commands

```powershell
pip install -r pipeline/requirements.txt
pytest pipeline/tests                        # the pipeline's own tests (sample inputs)

# build one run from raw outputs (CI calls this)
python -m pipeline.build --raw raw --site site --run-id 123-1 --sha <commit> \
    --branch main --trigger push [--bugs cart_rounding] [--keep 30] [--dashboard-url URL]

# run the suites locally like CI, then build (backend :8000 and preview :4173 running)
python -m pipeline.local_run [--suites unit,api,ui,perf] [--bugs a,b] [--perf-duration 20]
```

## Rules the pipeline applies

- **Retries become one result.** pytest-rerunfailures writes each attempt as its own JUnit
  `<testcase>`. The last attempt decides the status. A test that failed and then passed on
  retry is `flaky`, and the artifacts from all its attempts are kept.
- **Pass rate** is (passed + flaky) / (total − skipped).
- **Unit tests are kept separate.** `junit-unit*.xml` files hold the backend unit tests.
  Their ids are prefixed `store/backend/` and their layer is `unit`, so the dashboard can
  show them in their own section.
- **Catalog lookup across browsers.** Catalogs are collected once, with Chromium ids. A
  Firefox or WebKit result is matched to the same test's Chromium entry.
- **Artifact paths are normalised** to start at `test-results/`, however pytest recorded
  them. They're then copied to `reports/<run_id>/artifacts/` and linked from the run file.
- **Flaky analysis** uses only runs **without** injected bugs:
  - **Same-commit conflicts:** a test passed in one run and failed in another on the same
    commit.
  - **Retry-flaky:** a test passed only on retry within a run.
  - **30-day flip rate:** status changes between consecutive runs ÷ (runs − 1), over the
    30 days before the newest run.
- **Retention.** The newest `--keep` runs (default 30) keep their `reports/` folder. Older
  runs lose their downloads and artifact links but keep their per-test statuses, so history
  and flaky analysis still work.
- **If Allure isn't available**, the build still succeeds without the Allure download. It's
  found via `ALLURE_CMD`, then `allure` on PATH, then `%USERPROFILE%\tools\allure-2.46.1`.

## Size budget

Measured from real local runs: a run file is about 110 KB, the Allure zip about 1.5–1.8 MB,
the JUnit zip under 10 KB and the PDF about 2 KB. Failed UI attempts add a trace of about
330–470 KB and a screenshot of 37–80 KB each. A clean run is about 1.7 MB, so 30 runs keeping
full reports come to roughly 50–100 MB, depending on how many UI failures there are. That's
comfortably under GitHub Pages' published-site limit. (I assumed that limit is 1 GB; check
the current GitHub docs.)
