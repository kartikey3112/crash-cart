"""A thin API client for the store: one method per endpoint, always returning the raw
httpx.Response so tests decide what to assert (status, headers, schema)."""

import httpx


class StoreClient:
    def __init__(self, base_url: str, extra_headers: dict[str, str] | None = None):
        # extra_headers carries the run-wide bug switches (empty on a normal run).
        self.http = httpx.Client(base_url=base_url, headers=extra_headers or {}, timeout=30)
        self.token: str | None = None

    def close(self) -> None:
        self.http.close()

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", None) or {})
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        return self.http.request(method, path, headers=headers, **kwargs)

    # ---- auth ----
    def register(self, email: str, password: str, full_name: str = "API Tester") -> httpx.Response:
        body = {"email": email, "password": password, "full_name": full_name}
        return self.request("POST", "/auth/register", json=body)

    def login(self, email: str, password: str) -> httpx.Response:
        response = self.request("POST", "/auth/login", json={"email": email, "password": password})
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        return response

    def me(self) -> httpx.Response:
        return self.request("GET", "/auth/me")

    # ---- catalog ----
    def health(self) -> httpx.Response:
        return self.request("GET", "/health")

    def categories(self) -> httpx.Response:
        return self.request("GET", "/categories")

    def products(self, **params) -> httpx.Response:
        return self.request("GET", "/products", params=params)

    def product(self, product_id: int) -> httpx.Response:
        return self.request("GET", f"/products/{product_id}")

    # ---- cart ----
    def cart(self) -> httpx.Response:
        return self.request("GET", "/cart")

    def add_to_cart(self, product_id: int, quantity: int = 1) -> httpx.Response:
        body = {"product_id": product_id, "quantity": quantity}
        return self.request("POST", "/cart/items", json=body)

    def update_cart_item(self, product_id: int, quantity: int) -> httpx.Response:
        return self.request("PATCH", f"/cart/items/{product_id}", json={"quantity": quantity})

    def remove_cart_item(self, product_id: int) -> httpx.Response:
        return self.request("DELETE", f"/cart/items/{product_id}")

    def apply_coupon(self, code: str) -> httpx.Response:
        return self.request("PUT", "/cart/coupon", json={"code": code})

    def remove_coupon(self) -> httpx.Response:
        return self.request("DELETE", "/cart/coupon")

    # ---- checkout / orders ----
    def checkout(
        self, shipping: dict, card: dict, idempotency_key: str | None = None
    ) -> httpx.Response:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        body = {"shipping": shipping, "card": card}
        return self.request("POST", "/checkout", json=body, headers=headers)

    def orders(self) -> httpx.Response:
        return self.request("GET", "/orders")

    def order(self, order_id: int) -> httpx.Response:
        return self.request("GET", f"/orders/{order_id}")

    # ---- admin ----
    def admin_products(self) -> httpx.Response:
        return self.request("GET", "/admin/products")

    def admin_create_product(self, body: dict) -> httpx.Response:
        return self.request("POST", "/admin/products", json=body)

    def admin_update_product(self, product_id: int, body: dict) -> httpx.Response:
        return self.request("PATCH", f"/admin/products/{product_id}", json=body)

    def admin_delete_product(self, product_id: int) -> httpx.Response:
        return self.request("DELETE", f"/admin/products/{product_id}")
