# CrashCart store frontend

React 19 + Vite + TypeScript. A plain single-page app that talks to the FastAPI backend.

## Run locally

Start the backend first (see `store/backend/README.md`), then:

```powershell
cd store/frontend
npm install
npm run dev          # http://localhost:5173
```

The API URL comes from `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`). Copy
`.env.example` to `.env.local` to change it.

| Command | What it does |
|---|---|
| `npm run dev` | Dev server on port 5173 (fixed: the backend's CORS list expects it) |
| `npm run typecheck` | TypeScript check only |
| `npm run build` | Typecheck, then production build into `dist/` |
| `npm run preview` | Serve the production build on port 4173 |

## Product images

All artwork is original SVG generated from the backend seed data, so it always matches
the catalog:

```powershell
python store/frontend/scripts/generate_images.py
```

## Selector conventions (for UI tests)

- Every interactive element (links, buttons, inputs, selects) has a `data-testid`.
- Test ids are kebab-case and named `<area>-<thing>`, e.g. `cart-item-quantity`, `checkout-error`.
- Repeated items share one test id and carry a data attribute to pick a specific one:
  - `product-card` and `cart-item` have `data-sku`.
  - `order-row` has `data-order-id`.
  - `admin-product-row` has `data-sku` and `data-product-id`.

  Example: `[data-testid="cart-item"][data-sku="PHN-003"]`.
- Error messages use `role="alert"` and a `*-error` test id. Success messages use `role="status"`.
- Forms use `noValidate`, so validation messages are rendered in the page (testable), not
  shown as browser pop-ups.

## Design choices that matter for testing

- **Catalog filters live in the URL** (`/?q=wireless&category=gaming&sort=price_desc&page=2`),
  so any result page can be opened directly.
- **The client checks formats only.** Quantity limits, card expiry, Luhn and coupon rules are
  decided by the server, so the backend bug switches show up in the UI.
- **Checkout sends an `Idempotency-Key`** that stays the same for the whole visit to the page,
  so a double submit returns the same order.
