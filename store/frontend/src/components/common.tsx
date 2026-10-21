import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/** Shows an error message in a consistent, testable way. Renders nothing when message is empty. */
export function ErrorMessage({ message, testId }: { message: string | null; testId: string }) {
  if (!message) return null;
  return (
    <p className="alert alert-error" role="alert" data-testid={testId}>
      {message}
    </p>
  );
}

export function Loading({ testId = "loading" }: { testId?: string }) {
  return (
    <p className="loading" data-testid={testId} aria-live="polite">
      Loading…
    </p>
  );
}

/** Sends logged-out visitors to /login, remembering where they wanted to go. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading testId="auth-loading" />;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return children;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user?.role !== "admin") {
    return (
      <p className="alert alert-error" data-testid="admin-forbidden">
        You need an admin account to see this page.
      </p>
    );
  }
  return children;
}

export function DemoPaymentBanner() {
  return (
    <div className="alert alert-demo" role="note" data-testid="demo-payment-banner">
      <strong>Demo checkout.</strong> This is a fictional store: no real payment is taken and
      no card details are stored. Use test card <code>4242 4242 4242 4242</code> with any future
      expiry date and any 3-digit CVV.
    </div>
  );
}
