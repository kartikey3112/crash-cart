import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { Order } from "../api/types";
import { ErrorMessage, Loading } from "../components/common";
import { formatCents, formatDate } from "../utils/format";
import { TotalsTable } from "./CartPage";

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .orders()
      .then(setOrders)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load orders"));
  }, []);

  if (error) return <ErrorMessage message={error} testId="orders-error" />;
  if (!orders) return <Loading testId="orders-loading" />;

  return (
    <section data-testid="orders-page">
      <h1>Your orders</h1>
      {orders.length === 0 ? (
        <p className="empty" data-testid="orders-empty">
          You haven't placed any orders yet.{" "}
          <Link to="/" data-testid="orders-empty-shop-link">
            Start shopping
          </Link>
        </p>
      ) : (
        <table className="table" data-testid="orders-table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Placed</th>
              <th>Items</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id} data-testid="order-row" data-order-id={order.id}>
                <td>
                  <Link to={`/orders/${order.id}`} data-testid="order-row-link">
                    #{order.id}
                  </Link>
                </td>
                <td data-testid="order-row-date">{formatDate(order.created_at)}</td>
                <td data-testid="order-row-items">{order.items.reduce((n, i) => n + i.quantity, 0)}</td>
                <td data-testid="order-row-total">{formatCents(order.total_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function OrderDetailPage() {
  const { orderId } = useParams();
  const [params] = useSearchParams();
  const justPlaced = params.get("placed") === "1";
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .order(Number(orderId))
      .then(setOrder)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load order"));
  }, [orderId]);

  if (error) return <ErrorMessage message={error} testId="order-error" />;
  if (!order) return <Loading testId="order-loading" />;

  return (
    <section data-testid="order-detail" data-order-id={order.id}>
      {justPlaced && (
        <div className="alert alert-success" role="status" data-testid="order-confirmation">
          Thanks! Your demo order has been placed. No payment was taken.
        </div>
      )}
      <h1>
        Order <span data-testid="order-id">#{order.id}</span>
      </h1>
      <p className="muted">
        Placed {formatDate(order.created_at)} · Status{" "}
        <span className="tag" data-testid="order-status">
          {order.status}
        </span>{" "}
        · Card ending <span data-testid="order-card-last4">{order.card_last4}</span>
      </p>

      <div className="cart-layout">
        <table className="table" data-testid="order-items">
          <thead>
            <tr>
              <th>Product</th>
              <th>Price</th>
              <th>Qty</th>
              <th>Line total</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.product_id} data-testid="order-item">
                <td data-testid="order-item-name">{item.product_name}</td>
                <td>{formatCents(item.unit_price_cents)}</td>
                <td data-testid="order-item-quantity">{item.quantity}</td>
                <td>{formatCents(item.line_total_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <aside className="summary">
          <h2>Totals</h2>
          {order.coupon_code && (
            <p>
              Coupon <strong data-testid="order-coupon">{order.coupon_code}</strong>
            </p>
          )}
          <TotalsTable totals={order} testPrefix="order" />
          <h2>Ships to</h2>
          <p data-testid="order-shipping-address">{order.shipping_address}</p>
        </aside>
      </div>
      <p>
        <Link to="/orders" data-testid="back-to-orders">
          ← All orders
        </Link>
      </p>
    </section>
  );
}
