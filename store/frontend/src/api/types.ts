// Mirrors the backend's pydantic schemas (store/backend/app/schemas.py).

export type Role = "customer" | "admin";
export type SortOption = "name" | "price_asc" | "price_desc" | "newest";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  description: string;
  category: Category;
  price_cents: number;
  stock: number;
  image_path: string;
  created_at: string;
}

export interface AdminProduct extends Product {
  is_active: boolean;
  updated_at: string;
}

export interface ProductPage {
  items: Product[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ProductQuery {
  q?: string;
  category?: string;
  min_price_cents?: number;
  max_price_cents?: number;
  sort?: SortOption;
  page?: number;
  page_size?: number;
}

export interface Totals {
  subtotal_cents: number;
  discount_cents: number;
  tax_cents: number;
  shipping_cents: number;
  total_cents: number;
}

export interface CartLine {
  product_id: number;
  sku: string;
  name: string;
  image_path: string;
  unit_price_cents: number;
  quantity: number;
  line_total_cents: number;
  stock: number;
}

export interface Cart {
  items: CartLine[];
  coupon_code: string | null;
  totals: Totals;
}

export interface Shipping {
  full_name: string;
  address_line1: string;
  city: string;
  postal_code: string;
  country: string;
}

export interface Card {
  number: string;
  expiry: string;
  cvv: string;
  name_on_card: string;
}

export interface OrderItem {
  product_id: number;
  product_name: string;
  unit_price_cents: number;
  quantity: number;
  line_total_cents: number;
}

export interface Order extends Totals {
  id: number;
  status: string;
  items: OrderItem[];
  coupon_code: string | null;
  card_last4: string;
  shipping_address: string;
  created_at: string;
}

export interface ProductInput {
  sku: string;
  name: string;
  description: string;
  category_slug: string;
  price_cents: number;
  stock: number;
}
