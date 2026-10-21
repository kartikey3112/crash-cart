import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";

export function Layout() {
  const { user, logout } = useAuth();
  const { itemCount } = useCart();

  return (
    <div className="app">
      <header className="site-header" data-testid="site-header">
        <div className="container header-inner">
          <Link to="/" className="logo" data-testid="nav-logo" aria-label="CrashCart home">
            <img src="/img/logo.svg" alt="" width={36} height={36} />
            <span>CrashCart</span>
          </Link>
          <nav className="main-nav" aria-label="Main">
            <NavLink to="/" end data-testid="nav-shop">
              Shop
            </NavLink>
            {user && (
              <>
                <NavLink to="/cart" data-testid="nav-cart">
                  Cart{" "}
                  <span className="badge" data-testid="cart-count">
                    {itemCount}
                  </span>
                </NavLink>
                <NavLink to="/orders" data-testid="nav-orders">
                  Orders
                </NavLink>
              </>
            )}
            {user?.role === "admin" && (
              <NavLink to="/admin" data-testid="nav-admin">
                Admin
              </NavLink>
            )}
          </nav>
          <div className="account">
            {user ? (
              <>
                <span className="user-name" data-testid="nav-user-name">
                  {user.full_name}
                </span>
                <button type="button" className="btn btn-ghost" onClick={logout} data-testid="nav-logout">
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" data-testid="nav-login">
                  Log in
                </NavLink>
                <Link to="/register" className="btn btn-primary btn-small" data-testid="nav-register">
                  Sign up
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="container main" data-testid="main-content">
        <Outlet />
      </main>

      <footer className="site-footer" data-testid="site-footer">
        <div className="container">
          CrashCart is a fictional demo store built for automated testing. Products are not real
          and no payments are ever taken.
        </div>
      </footer>
    </div>
  );
}
