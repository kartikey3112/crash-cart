import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { CartLine, Totals } from "../api/types";
import { ErrorMessage, Loading } from "../components/common";
import { useCart } from "../context/CartContext";
import { formatCents } from "../utils/format";

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export function TotalsTable({ totals, testPrefix }: { totals: Totals; testPrefix: string }) {
  const rows: [string, string, number][] = [
    ["Subtotal", "subtotal", totals.subtotal_cents],
    ["Discount", "discount", -totals.discount_cents],
    ["Tax (8%)", "tax", totals.tax_cents],
    ["Shipping", "shipping", totals.shipping_cents],
  ];
  return (
    <dl className="totals">
      {rows.map(([label, key, cents]) => (
        <div key={key} className="totals-row">
          <dt>{label}</dt>
          <dd data-testid={`${testPrefix}-${key}`}>{formatCents(cents)}</dd>
        </div>
      ))}
      <div className="totals-row totals-grand">
        <dt>Total</dt>
        <dd data-testid={`${testPrefix}-total`}>{formatCents(totals.total_cents)}</dd>
      </div>
    </dl>
  );
}

function CartRow({ line, onError }: { line: CartLine; onError: (message: string | null) => void }) {
  const { setCart, refresh } = useCart();
  const [quantity, setQuantity] = useState(String(line.quantity));
  const [busy, setBusy] = useState(false);

  useEffect(() => setQuantity(String(line.quantity)), [line.quantity]);

  async function handleUpdate(event: FormEvent) {
    event.preventDefault();
    const qty = Number(quantity);
    if (!Number.isInteger(qty) || qty < 1) {
      onError("Quantity must be a whole number of at least 1");
      return;
    }
    setBusy(true);
    onError(null);
    try {
      setCart(await api.updateCartItem(line.product_id, qty));
    } catch (err) {
      onError(errorText(err, "Could not update quantity"));
      setQuantity(String(line.quantity));
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove() {
    setBusy(true);
    onError(null);
    try {
      await api.removeCartItem(line.product_id);
      // DELETE returns no body, so reload the cart to show what the server now holds.
      await refresh();
    } catch (err) {
      onError(errorText(err, "Could not remove item"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="cart-item" data-testid="cart-item" data-sku={line.sku} data-product-id={line.product_id}>
      <img src={line.image_path} alt="" className="cart-thumb" />
      <div className="cart-item-main">
        <Link to={`/products/${line.product_id}`} data-testid="cart-item-name">
          {line.name}
        </Link>
        <span className="muted" data-testid="cart-item-price">
          {formatCents(line.unit_price_cents)} each
        </span>
      </div>
      <form className="cart-qty" onSubmit={handleUpdate} noValidate>
        <label className="sr-only" htmlFor={`qty-${line.product_id}`}>
          Quantity
        </label>
        <input
          id={`qty-${line.product_id}`}
          type="number"
          min={1}
          max={99}
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          data-testid="cart-item-quantity"
        />
        <button type="submit" className="btn btn-ghost btn-small" disabled={busy} data-testid="cart-item-update">
          Update
        </button>
      </form>
      <span className="cart-line-total" data-testid="cart-item-line-total">
        {formatCents(line.line_total_cents)}
      </span>
      <button
        type="button"
        className="btn btn-link"
        onClick={handleRemove}
        disabled={busy}
        data-testid="cart-item-remove"
      >
        Remove
      </button>
    </li>
  );
}

export function CartPage() {
  const { cart, setCart, refresh } = useCart();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [couponCode, setCouponCode] = useState("");
  const [couponError, setCouponError] = useState<string | null>(null);

  // Always show fresh server state when the page opens (stock or prices may have changed).
  useEffect(() => {
    refresh().catch((err: unknown) => setError(errorText(err, "Could not load cart")));
  }, [refresh]);

  async function handleApplyCoupon(event: FormEvent) {
    event.preventDefault();
    if (!couponCode.trim()) return;
    setCouponError(null);
    try {
      setCart(await api.applyCoupon(couponCode.trim()));
      setCouponCode("");
    } catch (err) {
      setCouponError(errorText(err, "Could not apply coupon"));
    }
  }

  async function handleRemoveCoupon() {
    setCouponError(null);
    try {
      await api.removeCoupon();
      await refresh();
    } catch (err) {
      setCouponError(errorText(err, "Could not remove coupon"));
    }
  }

  if (!cart) return error ? <ErrorMessage message={error} testId="cart-error" /> : <Loading testId="cart-loading" />;

  if (cart.items.length === 0) {
    return (
      <section data-testid="cart-page">
        <h1>Your cart</h1>
        <p className="empty" data-testid="cart-empty">
          Your cart is empty.{" "}
          <Link to="/" data-testid="cart-empty-shop-link">
            Browse products
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section data-testid="cart-page">
      <h1>Your cart</h1>
      <ErrorMessage message={error} testId="cart-error" />
      <div className="cart-layout">
        <ul className="cart-items" data-testid="cart-items">
          {cart.items.map((line) => (
            <CartRow key={line.product_id} line={line} onError={setError} />
          ))}
        </ul>

        <aside className="summary" data-testid="cart-summary">
          <h2>Summary</h2>
          {cart.coupon_code ? (
            <p className="coupon-applied">
              Coupon <strong data-testid="coupon-applied">{cart.coupon_code}</strong>{" "}
              <button type="button" className="btn btn-link" onClick={handleRemoveCoupon} data-testid="coupon-remove">
                Remove
              </button>
            </p>
          ) : (
            <form className="coupon-form" onSubmit={handleApplyCoupon} noValidate>
              <label className="field field-grow">
                <span>Coupon code</span>
                <input value={couponCode} onChange={(e) => setCouponCode(e.target.value)} data-testid="coupon-input" />
              </label>
              <button type="submit" className="btn btn-ghost" data-testid="coupon-apply">
                Apply
              </button>
            </form>
          )}
          <ErrorMessage message={couponError} testId="coupon-error" />
          <TotalsTable totals={cart.totals} testPrefix="cart" />
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => navigate("/checkout")}
            data-testid="checkout-button"
          >
            Go to checkout
          </button>
        </aside>
      </div>
    </section>
  );
}
