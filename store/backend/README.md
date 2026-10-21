# CrashCart store backend

FastAPI + SQLite. The database is rebuilt from deterministic seed data on every start,
so the store always begins in a known state.

## Run locally

```powershell
cd store/backend
python -m venv .venv            # or reuse the repo-root .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs
- Spec: `openapi.json` (regenerate with `python -m app.export_openapi`; a unit test fails if it is stale)

## Test

```powershell
.venv\Scripts\python -m pytest --cov=app --cov-branch
.venv\Scripts\ruff check app tests
```

## Configuration

All settings are `CRASHCART_*` environment variables (see `.env.example`). With
`CRASHCART_ENVIRONMENT=production` the app refuses to start while any secret still has its
dev default, or if the JWT secret is shorter than 32 characters.

## Seeded accounts and data

| What | Value |
|---|---|
| Demo customer | `demo@crashcart.test` / `demo-password` (public on purpose) |
| Admin | from `CRASHCART_ADMIN_EMAIL` / `CRASHCART_ADMIN_PASSWORD` |
| Products | 48 active (4 pages of 12) + 1 soft-deleted |
| Coupons | `SAVE10`, `FLAT5` (min $20), `BIGSPEND20` (min $100), `EXPIRED15`, `USEDUP` |
| Test cards | `4242 4242 4242 4242` approved, `4000 0000 0000 0002` declined |

Payments are fake: card numbers are checked locally (Luhn, expiry, CVV) and nothing is charged.

## Bug switches

Send **both** headers to turn bugs on for one request:

```
X-Bug-Switches: cart_rounding,order_idor
X-Test-Token: <CRASHCART_TEST_TOKEN>
```

Without a valid token the switches header is ignored. With a valid token, an unknown switch
name returns 400 (so typos can't silently disable a bug). Active switches are echoed in the
`X-Bug-Switches-Active` response header.

| Switch | Effect |
|---|---|
| `cart_rounding` | Discount and tax truncated instead of rounded half-up |
| `search_ignores_filters` | Category/price filters dropped when `q` is present |
| `expired_card_accepted` | Card expiry check skipped |
| `slow_products` | `GET /products` sleeps (`CRASHCART_SLOW_BUG_DELAY_MS`, default 2000) |
| `pagination_off_by_one` | Page N+1 repeats the last product of page N |
| `coupon_expiry_ignored` | Expired coupons accepted |
| `stock_not_enforced` | Cart quantity may exceed stock |
| `order_idor` | `GET /orders/{id}` returns other users' orders |
| `checkout_double_submit` | `Idempotency-Key` ignored, so retries create duplicate orders |
| `sort_desc_broken` | `sort=price_desc` returns ascending order |
| `remove_item_noop` | `DELETE /cart/items/{id}` returns 204 but keeps the item |

## Endpoints

| Method | Path | Auth |
|---|---|---|
| GET | `/health` | – |
| POST | `/auth/register`, `/auth/login` | – |
| GET | `/auth/me` | customer |
| GET | `/categories`, `/products`, `/products/{id}` | – |
| GET/POST/PATCH/DELETE | `/cart`, `/cart/items`, `/cart/items/{product_id}` | customer |
| PUT/DELETE | `/cart/coupon` | customer |
| POST | `/checkout` (optional `Idempotency-Key` header) | customer |
| GET | `/orders`, `/orders/{id}` | customer |
| GET/POST/PATCH/DELETE | `/admin/products[/{id}]` | admin |
| POST | `/test/reset` | `X-Test-Token` |
| GET | `/test/bugs` | `X-Test-Token` |
