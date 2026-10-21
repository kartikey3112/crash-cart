import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { Card, Shipping } from "../api/types";
import { DemoPaymentBanner, ErrorMessage, Loading } from "../components/common";
import { useCart } from "../context/CartContext";
import { TotalsTable } from "./CartPage";

const EMPTY_SHIPPING: Shipping = { full_name: "", address_line1: "", city: "", postal_code: "", country: "" };
const EMPTY_CARD: Card = { number: "", expiry: "", cvv: "", name_on_card: "" };

// The client checks only the *format* of card fields. Whether the card is expired, valid
// (Luhn) or declined is decided by the server, so server-side bugs show up in the UI.
function clientCheck(shipping: Shipping, card: Card): string | null {
  if (Object.values(shipping).some((v) => !v.trim())) return "Please fill in every shipping field";
  if (!card.number.trim() || !card.name_on_card.trim()) return "Please fill in every card field";
  if (!/^\d{2}\/\d{2}$/.test(card.expiry)) return "Expiry must look like MM/YY";
  if (!/^\d{3}$/.test(card.cvv)) return "CVV must be 3 digits";
  return null;
}

export function CheckoutPage() {
  const { cart, refresh } = useCart();
  const navigate = useNavigate();
  const [shipping, setShipping] = useState(EMPTY_SHIPPING);
  const [card, setCard] = useState(EMPTY_CARD);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // One key per visit to this page: a double click or retry re-sends the same key, so the
  // server returns the first order instead of charging twice.
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  useEffect(() => {
    refresh().catch(() => setError("Could not load cart"));
  }, [refresh]);

  const onShipping = (field: keyof Shipping) => (e: ChangeEvent<HTMLInputElement>) =>
    setShipping((s) => ({ ...s, [field]: e.target.value }));
  const onCard = (field: keyof Card) => (e: ChangeEvent<HTMLInputElement>) =>
    setCard((c) => ({ ...c, [field]: e.target.value }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = clientCheck(shipping, card);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const order = await api.checkout(shipping, card, idempotencyKey);
      navigate(`/orders/${order.id}?placed=1`, { replace: true });
      // The server emptied the cart; refresh so the header badge drops to 0.
      refresh().catch(() => undefined);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Checkout failed");
    } finally {
      setBusy(false);
    }
  }

  if (!cart) return <Loading testId="checkout-loading" />;
  if (cart.items.length === 0) {
    return (
      <section data-testid="checkout-page">
        <h1>Checkout</h1>
        <p className="empty" data-testid="checkout-empty">
          Your cart is empty.{" "}
          <Link to="/" data-testid="checkout-empty-shop-link">
            Browse products
          </Link>
        </p>
      </section>
    );
  }

  return (
    <section data-testid="checkout-page">
      <h1>Checkout</h1>
      <DemoPaymentBanner />
      <form className="checkout-layout" onSubmit={handleSubmit} noValidate data-testid="checkout-form">
        <div className="checkout-fields">
          <fieldset>
            <legend>Shipping address</legend>
            <label className="field">
              <span>Full name</span>
              <input value={shipping.full_name} onChange={onShipping("full_name")} data-testid="shipping-name" />
            </label>
            <label className="field">
              <span>Address</span>
              <input value={shipping.address_line1} onChange={onShipping("address_line1")} data-testid="shipping-address" />
            </label>
            <div className="field-row">
              <label className="field">
                <span>City</span>
                <input value={shipping.city} onChange={onShipping("city")} data-testid="shipping-city" />
              </label>
              <label className="field">
                <span>Postal code</span>
                <input value={shipping.postal_code} onChange={onShipping("postal_code")} data-testid="shipping-postal" />
              </label>
              <label className="field">
                <span>Country</span>
                <input value={shipping.country} onChange={onShipping("country")} data-testid="shipping-country" />
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>Payment (demo only)</legend>
            <label className="field">
              <span>Card number</span>
              <input
                inputMode="numeric"
                autoComplete="off"
                value={card.number}
                onChange={onCard("number")}
                placeholder="4242 4242 4242 4242"
                data-testid="card-number"
              />
            </label>
            <div className="field-row">
              <label className="field">
                <span>Expiry (MM/YY)</span>
                <input autoComplete="off" value={card.expiry} onChange={onCard("expiry")} placeholder="12/30" data-testid="card-expiry" />
              </label>
              <label className="field">
                <span>CVV</span>
                <input inputMode="numeric" autoComplete="off" value={card.cvv} onChange={onCard("cvv")} data-testid="card-cvv" />
              </label>
            </div>
            <label className="field">
              <span>Name on card</span>
              <input autoComplete="off" value={card.name_on_card} onChange={onCard("name_on_card")} data-testid="card-name" />
            </label>
          </fieldset>
        </div>

        <aside className="summary" data-testid="checkout-summary">
          <h2>Order summary</h2>
          <ul className="summary-lines">
            {cart.items.map((line) => (
              <li key={line.product_id} data-testid="checkout-line">
                {line.quantity} × {line.name}
              </li>
            ))}
          </ul>
          <TotalsTable totals={cart.totals} testPrefix="checkout" />
          <ErrorMessage message={error} testId="checkout-error" />
          <button type="submit" className="btn btn-primary btn-block" disabled={busy} data-testid="place-order">
            {busy ? "Placing order…" : "Place order"}
          </button>
        </aside>
      </form>
    </section>
  );
}
