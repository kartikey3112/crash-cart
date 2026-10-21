import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/endpoints";
import type { Cart } from "../api/types";
import { useAuth } from "./AuthContext";

interface CartState {
  cart: Cart | null;
  itemCount: number;
  refresh: () => Promise<void>;
  setCart: (cart: Cart | null) => void;
}

const CartContext = createContext<CartState | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);

  const refresh = useCallback(async () => {
    if (!user) {
      setCart(null);
      return;
    }
    setCart(await api.cart());
  }, [user]);

  // Reload whenever the logged-in user changes (login, logout, switching accounts).
  useEffect(() => {
    refresh().catch(() => setCart(null));
  }, [refresh]);

  const itemCount = cart ? cart.items.reduce((sum, line) => sum + line.quantity, 0) : 0;
  const value = useMemo(
    () => ({ cart, itemCount, refresh, setCart }),
    [cart, itemCount, refresh],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartState {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside <CartProvider>");
  return context;
}
