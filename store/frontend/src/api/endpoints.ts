// One function per backend endpoint, so components never build URLs themselves.
import { request, toQueryString } from "./client";
import type {
  AdminProduct,
  Card,
  Cart,
  Category,
  Order,
  Product,
  ProductInput,
  ProductPage,
  ProductQuery,
  Shipping,
  Token,
  User,
} from "./types";

export const api = {
  register: (email: string, password: string, full_name: string) =>
    request<User>("/auth/register", { method: "POST", body: { email, password, full_name } }),
  login: (email: string, password: string) =>
    request<Token>("/auth/login", { method: "POST", body: { email, password } }),
  me: () => request<User>("/auth/me"),

  categories: () => request<Category[]>("/categories"),
  products: (query: ProductQuery) => request<ProductPage>(`/products${toQueryString(query)}`),
  product: (id: number) => request<Product>(`/products/${id}`),

  cart: () => request<Cart>("/cart"),
  addToCart: (product_id: number, quantity: number) =>
    request<Cart>("/cart/items", { method: "POST", body: { product_id, quantity } }),
  updateCartItem: (productId: number, quantity: number) =>
    request<Cart>(`/cart/items/${productId}`, { method: "PATCH", body: { quantity } }),
  removeCartItem: (productId: number) =>
    request<void>(`/cart/items/${productId}`, { method: "DELETE" }),
  applyCoupon: (code: string) => request<Cart>("/cart/coupon", { method: "PUT", body: { code } }),
  removeCoupon: () => request<void>("/cart/coupon", { method: "DELETE" }),

  checkout: (shipping: Shipping, card: Card, idempotencyKey: string) =>
    request<Order>("/checkout", {
      method: "POST",
      body: { shipping, card },
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  orders: () => request<Order[]>("/orders"),
  order: (id: number) => request<Order>(`/orders/${id}`),

  adminProducts: () => request<AdminProduct[]>("/admin/products"),
  adminCreateProduct: (input: ProductInput) =>
    request<AdminProduct>("/admin/products", { method: "POST", body: input }),
  adminUpdateProduct: (id: number, input: Partial<ProductInput>) =>
    request<AdminProduct>(`/admin/products/${id}`, { method: "PATCH", body: input }),
  adminDeleteProduct: (id: number) =>
    request<void>(`/admin/products/${id}`, { method: "DELETE" }),
};
