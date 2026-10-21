# CI: how the test pipeline works

One workflow, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), tests the store and
publishes the results dashboard.

## When it runs

| Trigger | What runs |
|---|---|
| Push to `main` (except docs-only changes) | Self-test, then every live suite on Chromium. Waits until Render and Vercel serve the pushed commit. |
| Nightly, 21:07 UTC (02:37 IST) | Self-test, then every live suite on Chromium. No deploy wait. GitHub may delay scheduled runs when it's busy. |
| Manual ("Run workflow") | Self-test, then the chosen `suites`, `browsers` and `bugs`. Typos fail the run immediately. |

**One run at a time.** A new run waits for the current one instead of cancelling it.
GitHub keeps only **one** waiting run per group: if a third arrives while one is running and
one is waiting, the waiting one is cancelled.

## Jobs

```
self-test ───────────────────────────────────────┐
plan → prepare → live-api → live-ui → live-perf ─┴─► publish ─► deploy (GitHub Pages)
```

| Job | What it does | Permissions |
|---|---|---|
| `self-test` | Runs ruff, actionlint (with ShellCheck), the frontend type-check and build, the backend unit tests, and the API suite against a backend started **inside the runner** under coverage (combined into unit + API coverage). Then the pipeline and dashboard test suites, and an upload of the raw results. | read |
| `plan` | Turns the trigger and inputs into which suites, browsers and bug switches to run (`pipeline/ci_plan.py`). Skips live testing if the URL secrets aren't set yet. | read |
| `prepare` | Waits for the deployed backend to wake up (free tier). After a push, waits until `/health` and `/version.json` report the pushed commit. Then resets the store **once** (`pipeline/ci_wait.py`). | read |
| `live-api` | API suite against the deployed backend, 4 workers, `RESET_BEFORE_RUN=false`. | read |
| `live-ui` | UI suite against the deployed frontend, one browser at a time, one retry (pass-on-retry is reported as flaky), traces and screenshots kept. | read |
| `live-perf` | JMeter scenarios (JMeter 5.6.3 from the Apache archive, SHA-512 checked, on JDK 17). Budgets come from repository variables. | read |
| `publish` | Merges all raw results, loads the history from the `results-data` branch, builds the dashboard data and downloads (Allure CLI from Maven Central, SHA-512 checked), and force-pushes the history as one commit. Deploys only if the dashboard tests passed. | contents: write |
| `deploy` | Publishes the site to GitHub Pages. | pages: write, id-token: write |

**Why the live suites run in sequence:**
- The API admin tests create products, which would shift the pages the UI pagination test
  compares.
- Perf runs last so other suites' traffic can't skew its numbers.

Every suite job still runs if the previous one failed, so results are always collected.

**Dashboard gate.** If the dashboard's own tests fail, the run's results are still saved to
`results-data`, but the site isn't deployed and the workflow run is marked failed.

## Secrets (Settings → Secrets and variables → Actions → **Secrets** → *Repository secrets*)

Use **repository** secrets. Environment secrets only reach jobs that declare that environment,
and the test jobs don't declare one, so the secrets would arrive empty.

| Secret | Value | Must match |
|---|---|---|
| `STORE_API_URL` | Backend URL, no trailing slash, e.g. `https://<service>.onrender.com` | Render service URL |
| `STORE_UI_URL` | Frontend URL, no trailing slash, e.g. `https://<project>.vercel.app` | Vercel production URL |
| `TEST_TOKEN` | Long random string (see below) | Render `CRASHCART_TEST_TOKEN` |
| `ADMIN_EMAIL` | The seeded admin's email | Render `CRASHCART_ADMIN_EMAIL` |
| `ADMIN_PASSWORD` | The seeded admin's password | Render `CRASHCART_ADMIN_PASSWORD` |

Generate tokens and passwords with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Until `STORE_API_URL` and `STORE_UI_URL` exist, live testing is skipped and the dashboard
shows only the self-test results.

## Variables (Settings → Secrets and variables → Actions → **Variables**). All optional.

| Variable | Default | Meaning |
|---|---|---|
| `PERF_USERS` | 10 | Concurrent JMeter users per scenario |
| `PERF_DURATION_S` | 60 | Seconds per scenario |
| `PERF_P95_MS_PRODUCTS_LIST` | 800 | p95 budget for `GET /products` |
| `PERF_P95_MS_PRODUCT_SEARCH` | 800 | p95 budget for a filtered search |
| `PERF_P95_MS_PRODUCT_DETAIL` | 800 | p95 budget for `GET /products/{id}` |
| `PERF_P95_MS_CART_READ` | 800 | p95 budget for `GET /cart` |

These are set from a measured Render baseline in Phase 9.

## Repository settings

1. **Settings → Pages → Build and deployment → Source: "GitHub Actions".** This creates the
   `github-pages` environment the `deploy` job uses. That environment only allows deploys
   from `main`, so start manual runs from `main`.
2. **Settings → Actions → General → Workflow permissions:** the default "Read repository
   contents" is fine. Jobs that need write access ask for it in the workflow.
3. **Don't protect `results-data`.** CI force-pushes a single fresh commit there on every run.
   If you add a branch ruleset, exclude `results-data` or allow GitHub Actions to force-push.
4. **Actions must be allowed to run.** Settings → Actions → General → "Allow all actions",
   or at least GitHub-authored ones (all actions used are `actions/*`).

## Checks that only the first real run can prove

These steps can't be exercised on a Windows machine:
- the backend running under coverage in the background on Linux, stopped with SIGINT
- `playwright install --with-deps`
- `npm ci` on the runner
- every `actions/*` step
- the Pages deployment
- the force-push to `results-data`

Each was written to fail loudly with a clear message if something is off.

## Local equivalents

| CI job | Local command |
|---|---|
| `self-test` lint | `ruff check . store/backend` and `actionlint` |
| Unit tests | `cd store/backend; pytest --cov` |
| Live suites + publish | `python -m pipeline.local_run` (backend :8000 and preview :4173 running) |
| Pipeline / dashboard tests | `pytest pipeline/tests` / `pytest dashboard/tests` |
