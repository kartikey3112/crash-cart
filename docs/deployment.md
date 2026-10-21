# Deployment guide (all free tiers)

| Piece | Host | Configured by |
|---|---|---|
| Store backend (FastAPI + SQLite) | Render free web service | [`render.yaml`](../render.yaml) Blueprint |
| Store frontend (React build) | Vercel Hobby | Vercel dashboard + [`store/frontend/vercel.json`](../store/frontend/vercel.json) |
| Results dashboard | GitHub Pages | The CI workflow ([docs/ci.md](ci.md)) |

Order matters a little: Render and Vercel import the code from GitHub, and each needs the
other's URL (CORS and the API base URL).

## 1. Push the code to GitHub

```powershell
git remote add origin https://github.com/kartikey3112/crash-cart.git
git push -u origin main
```

The first CI run starts right away. With no URL secrets yet, it runs the self-test, skips the
live suites, and fails at the deploy step until Pages is enabled (step 5). That's expected.

## 2. Backend on Render

1. In Render, choose **New → Blueprint**, connect GitHub, and pick `crash-cart`. Render reads
   `render.yaml` and proposes the `crashcart-api` service on the **Free** plan.
2. When asked for the `sync: false` values, enter:
   - `CRASHCART_TEST_TOKEN`: a new random token (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   - `CRASHCART_ADMIN_EMAIL`: e.g. `admin@crashcart.test`
   - `CRASHCART_ADMIN_PASSWORD`: a new random password
   - `CRASHCART_CORS_ORIGINS`: leave it as a placeholder such as `http://localhost:4173` for
     now. It gets the Vercel URL in step 4.

   Keep these values: the same values go into the GitHub secrets in step 5.
3. Apply, wait for the first deploy, and note the URL (`https://crashcart-api-….onrender.com`).
4. **Check:** open `<url>/health`. It should show `{"status":"ok", …, "commit":"<sha>"}`,
   where the commit matches your latest commit on GitHub.

Free-tier behaviour to expect:
- The service sleeps after about 15 minutes idle, and the first request then takes up to a
  minute.
- Every deploy or restart re-seeds the SQLite data.

## 3. Frontend on Vercel

1. In Vercel, choose **Add New → Project**, import `crash-cart`, and set **Root Directory** to
   `store/frontend`. Vercel detects Vite.
2. Add an environment variable: `VITE_API_BASE_URL` = the Render URL (no trailing slash).
3. **Settings → Git → Ignored Build Step → "Only build production".** CI pushes a
   `results-data` branch on every run (it holds only the dashboard data). Without this
   setting, Vercel tries to build that branch as a preview, fails because it has no
   `store/frontend`, and emails you a failure after every run.
4. Deploy and note the URL (`https://<project>.vercel.app`).
5. **Check:** `<url>/version.json` shows `{"commit":"<sha>"}`, and the shop loads products.

## 4. Point the backend's CORS at the frontend

In Render, open the service, go to **Environment**, and set `CRASHCART_CORS_ORIGINS` to the
Vercel URL. Save; Render redeploys. Then reload the shop: products should load without CORS
errors in the browser console.

## 5. GitHub settings, secrets and Pages

Details: [docs/ci.md](ci.md).

- **Settings → Secrets and variables → Actions → Secrets → "New repository secret".** Use
  **repository** secrets, not environment secrets: the test jobs don't use a GitHub
  environment, so environment secrets would reach them empty.
  - `STORE_API_URL`, `STORE_UI_URL`
  - `TEST_TOKEN`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` (the same values as on Render)
- **Settings → Pages → Source: GitHub Actions.**

## 6. First full run and perf baseline

1. **Actions → CrashCart tests → Run workflow** with the defaults.
2. Check the dashboard at `https://kartikey3112.github.io/crash-cart/`.
3. Read the perf p95 values from that run and set the `PERF_P95_MS_*` repository variables
   (budget = measured p95 plus headroom).
4. Run the workflow manually with `bugs: cart_rounding` to prove the whole pipeline end to end.
