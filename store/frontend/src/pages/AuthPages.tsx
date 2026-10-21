import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/common";
import { useAuth } from "../context/AuthContext";

/** Only follow same-site paths from ?next=, so the login page can't redirect to another site. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={next} replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!email || !password) {
      setError("Enter your email and password");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(errorText(err, "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-card" data-testid="login-page">
      <h1>Log in</h1>
      <form onSubmit={handleSubmit} noValidate data-testid="login-form">
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            data-testid="login-email"
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            data-testid="login-password"
          />
        </label>
        <ErrorMessage message={error} testId="login-error" />
        <button type="submit" className="btn btn-primary btn-block" disabled={busy} data-testid="login-submit">
          Log in
        </button>
      </form>
      <p className="hint" data-testid="login-demo-hint">
        Just looking? Use the demo account <code>demo@crashcart.test</code> /{" "}
        <code>demo-password</code>.
      </p>
      <p>
        New here?{" "}
        <Link to={`/register?next=${encodeURIComponent(next)}`} data-testid="login-register-link">
          Create an account
        </Link>
      </p>
    </section>
  );
}

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={next} replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!fullName || !email || !password) {
      setError("All fields are required");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await register(email, password, fullName);
      navigate(next, { replace: true });
    } catch (err) {
      setError(errorText(err, "Registration failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-card" data-testid="register-page">
      <h1>Create an account</h1>
      <form onSubmit={handleSubmit} noValidate data-testid="register-form">
        <label className="field">
          <span>Full name</span>
          <input
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            data-testid="register-name"
          />
        </label>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            data-testid="register-email"
          />
        </label>
        <label className="field">
          <span>Password (at least 8 characters)</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            data-testid="register-password"
          />
        </label>
        <ErrorMessage message={error} testId="register-error" />
        <button type="submit" className="btn btn-primary btn-block" disabled={busy} data-testid="register-submit">
          Sign up
        </button>
      </form>
      <p>
        Already have an account? <Link to="/login" data-testid="register-login-link">Log in</Link>
      </p>
    </section>
  );
}
