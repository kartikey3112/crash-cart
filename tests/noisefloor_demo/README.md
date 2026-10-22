# Noisefloor demo tests

Tests that are **flaky or slow on purpose**. They feed Noisefloor, a separate project
that reads Jenkins build
history to find flaky tests and runtime regressions. They live only on the `noisefloor-demo`
branch and are **skipped unless `NOISEFLOOR_DEMO=1`**, so CrashCart's own CI never runs them.

| File | What it holds |
|---|---|
| `test_demo_flaky.py` | 6 flaky tests with realistic causes, plus 1 stable test that leaks state |
| `test_demo_slow.py` | 4 tests that always pass but get slower at known commits |
| `workload.py` | the stand-in store code the slow tests call (simulated call costs) |
| `expected.json` | the answer key: designed failure rates and which commit slows which test |

## How the randomness works

Outcomes are seeded from the build number (`BUILD_NUMBER`, which Jenkins sets). For example,
build 7 of `test_demo_bulk_discount_for_random_quantity` always picks the same quantity, so
history can be rebuilt exactly. Builds 7 and 8 on the same commit can still disagree, which
is what makes a test flaky.

## Run locally

The backend must be running (see `tests/README.md`), because the shared session setup checks it.

```powershell
$env:NOISEFLOOR_DEMO = "1"; $env:NOISEFLOOR_DEMO_SEED = "7"
pytest tests/noisefloor_demo -o junit_suite_name=demo --junitxml=junit-demo.xml
```
