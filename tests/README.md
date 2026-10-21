# CrashCart system tests

These tests run against a live store (local or deployed), not in-process. Backend unit tests
are separate, in `store/backend/tests`.

| Layer | Folder | Tools |
|---|---|---|
| API | `tests/api` | pytest + httpx, responses validated with pydantic contracts |
| UI | `tests/ui` | pytest-playwright (Phase 4) |
| Perf | `tests/perf` | JMeter driven from pytest (Phase 5) |

## Run locally

```powershell
pip install -r tests/requirements.txt
# start the backend (see store/backend/README.md), then from the repo root:
pytest tests/api                 # serial
pytest tests/api -n 4            # 4 parallel workers
pytest tests/api --alluredir=allure-results --junitxml=junit-api.xml
```

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `API_BASE_URL` | `http://127.0.0.1:8000` | Backend under test |
| `UI_BASE_URL` | `http://localhost:5173` | Frontend under test |
| `TEST_TOKEN` | `dev-test-token` | Must match the backend's `CRASHCART_TEST_TOKEN` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | dev defaults | Seeded admin account |
| `WAKE_TIMEOUT_S` | `120` | How long to wait for a sleeping free-tier backend |
| `RESET_BEFORE_RUN` | `true` | Reset the store to its seed state at session start |
| `ENABLE_BUGS` | (empty) | Comma-separated bug switches to turn on for every request |

## What happens at session start

1. **Wait for the backend.** `/health` is polled until it answers ok. If it doesn't within
   `WAKE_TIMEOUT_S`, the run stops with exit code 3 and the last connection error.
2. **Reset the data.** `POST /test/reset` restores the seed state, once per run. This runs on
   the xdist controller only, so parallel workers never reset each other's data.
3. **Check every test's metadata.** Each test needs exactly one layer marker
   (`api`/`ui`/`perf`), a `feature("...")` marker and a docstring. Any `bug("...")` name must
   be a real switch. Otherwise the run stops with exit code 4. The dashboard's test catalog
   is generated from this metadata:

   ```powershell
   pytest tests --collect-only -q --catalog-out=catalog.json
   ```

## Test design rules

- **Tests assert correct behaviour.** A test tagged `@pytest.mark.bug("x")` passes on the
  healthy store and fails when switch `x` is on.
- **Contracts are independent of the backend code.** `tests/api/schemas.py` uses
  `extra="forbid"`, so a new, renamed or leaked field fails validation.
  `tests/api/pricing_oracle.py` recalculates totals from the business rules instead of
  trusting the server.
- **Parallel-safe data.** Each test registers its own users, and seeded products have fixed
  roles (see `tests/api/data.py`). Assertions use invariants ("sorted", "no duplicates",
  "seeded SKUs present") rather than global counts that a parallel test could change.
- **Failure messages explain themselves.** `expect_status` and `expect_error` include the
  request and response body.

## Proving the bug switches

```powershell
python -m tests.tools.prove_bug_switches --suite tests/api
```

This runs a baseline (everything must pass), then the suite once per switch with only that
switch enabled. For each switch it reports which targeted tests failed. It exits non-zero if
the baseline isn't green or any targeted switch goes uncaught.
