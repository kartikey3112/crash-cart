"""Plain helper functions and constants for backend unit tests (fixtures live in conftest.py)."""

from fastapi.testclient import TestClient

UNIT_TEST_TOKEN = "unit-test-token"
ADMIN_EMAIL = "admin@unit.test"
ADMIN_PASSWORD = "unit-admin-password"
APPROVED_CARD = {
    "number": "4242 4242 4242 4242",
    "expiry": "12/99",
    "cvv": "123",
    "name_on_card": "Test Buyer",
}
SHIPPING = {
    "full_name": "Test Buyer",
    "address_line1": "1 Test Street",
    "city": "Testville",
    "postal_code": "12345",
    "country": "IN",
}


def bug_headers(*bugs: str) -> dict[str, str]:
    return {"X-Bug-Switches": ",".join(bugs), "X-Test-Token": UNIT_TEST_TOKEN}


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def product_id(client: TestClient, sku: str) -> int:
    """Look up a seeded product's id by SKU (ids are an implementation detail)."""
    # All 48 active products fit on one page of 50.
    items = client.get("/products", params={"page_size": 50}).json()["items"]
    for item in items:
        if item["sku"] == sku:
            return item["id"]
    raise LookupError(sku)


def add_to_cart(client: TestClient, headers: dict, sku: str, quantity: int = 1):
    return client.post(
        "/cart/items",
        json={"product_id": product_id(client, sku), "quantity": quantity},
        headers=headers,
    )


def checkout(client: TestClient, headers: dict, card: dict | None = None, **kwargs):
    body = {"shipping": SHIPPING, "card": card or APPROVED_CARD}
    return client.post("/checkout", json=body, headers=headers, **kwargs)
