import pytest

from app.security import create_access_token
from tests.helpers import UNIT_TEST_TOKEN, login

pytestmark = pytest.mark.unit


def _register(client, email="new@unit.test", password="password123", full_name="New User"):
    return client.post(
        "/auth/register", json={"email": email, "password": password, "full_name": full_name}
    )


# ---------------- auth ----------------


@pytest.mark.feature("auth")
def test_register_returns_customer_without_password(client):
    """Registering returns 201 with a customer profile and never exposes the password hash."""
    response = _register(client, email="Mixed.Case@Unit.Test")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "mixed.case@unit.test"
    assert body["role"] == "customer"
    assert "password" not in str(body)


@pytest.mark.feature("auth")
def test_duplicate_email_is_409_case_insensitive(client):
    """An email that differs only by case counts as already registered."""
    _register(client, email="dup@unit.test")
    response = _register(client, email="DUP@unit.test")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "email_taken"


@pytest.mark.feature("auth")
@pytest.mark.parametrize(
    ("password", "status"),
    [("a" * 7, 422), ("a" * 8, 201), ("a" * 72, 201), ("a" * 73, 422), ("é" * 37, 422)],
)
def test_password_length_boundaries(client, password, status):
    """Passwords need 8+ characters and at most 72 bytes (bcrypt's limit); 37 'é' is 74 bytes."""
    assert _register(client, password=password).status_code == status


@pytest.mark.feature("auth")
@pytest.mark.parametrize("email", ["no-at-sign", "a@b", "spaces in@x.com", ""])
def test_malformed_email_is_422(client, email):
    """Obviously malformed emails are rejected."""
    assert _register(client, email=email).status_code == 422


@pytest.mark.feature("auth")
def test_login_and_me(client):
    """Logging in returns a bearer token that /auth/me accepts."""
    _register(client, email="me@unit.test")
    headers = login(client, "me@unit.test", "password123")
    assert client.get("/auth/me", headers=headers).json()["email"] == "me@unit.test"


@pytest.mark.feature("auth")
@pytest.mark.parametrize(
    ("email", "password"), [("me@unit.test", "wrong-password"), ("nobody@unit.test", "x" * 8)]
)
def test_bad_login_gives_same_401(client, email, password):
    """Wrong password and unknown email give the identical error (no account enumeration)."""
    _register(client, email="me@unit.test")
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"


@pytest.mark.feature("auth")
def test_me_without_token_is_401(client):
    """/auth/me without a token is 401 and advertises the Bearer scheme."""
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.feature("auth")
def test_tampered_token_is_401(client, customer):
    """Changing one character of the token's signature makes it invalid."""
    token = customer["Authorization"]
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert client.get("/auth/me", headers={"Authorization": tampered}).status_code == 401


@pytest.mark.feature("auth")
def test_expired_token_is_401(client, settings):
    """A correctly signed token whose expiry has passed is rejected."""
    token = create_access_token(1, "admin", settings.jwt_secret, expire_minutes=-1)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.feature("auth")
def test_token_signed_with_other_secret_is_401(client):
    """A token signed with someone else's secret is rejected, even for a real user id."""
    token = create_access_token(1, "admin", "attacker-secret-" + "x" * 32, expire_minutes=5)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ---------------- admin ----------------

NEW_PRODUCT = {
    "sku": "TST-001",
    "name": "Unit Test Gadget",
    "category_slug": "gaming",
    "price_cents": 1234,
    "stock": 5,
}


@pytest.mark.feature("admin")
def test_customer_cannot_use_admin_api(client, customer):
    """Admin endpoints return 403 for a logged-in customer."""
    assert client.post("/admin/products", json=NEW_PRODUCT, headers=customer).status_code == 403


@pytest.mark.feature("admin")
def test_admin_creates_product_visible_in_catalog(client, admin):
    """A product created by an admin shows up in public search."""
    assert client.post("/admin/products", json=NEW_PRODUCT, headers=admin).status_code == 201
    assert client.get("/products", params={"q": "Unit Test Gadget"}).json()["total"] == 1


@pytest.mark.feature("admin")
@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"price_cents": 0}, 422),
        ({"price_cents": -1}, 422),
        ({"stock": -1}, 422),
        ({"sku": "bad"}, 422),
        ({"category_slug": "nope"}, 422),
        ({"sku": "AUD-001"}, 409),
    ],
)
def test_admin_create_validation(client, admin, change, status):
    """Invalid price, stock, SKU format and unknown category are 422; a duplicate SKU is 409."""
    response = client.post("/admin/products", json={**NEW_PRODUCT, **change}, headers=admin)
    assert response.status_code == status


@pytest.mark.feature("admin")
def test_admin_partial_update(client, admin):
    """PATCH changes only the fields sent."""
    pid = client.post("/admin/products", json=NEW_PRODUCT, headers=admin).json()["id"]
    body = client.patch(f"/admin/products/{pid}", json={"price_cents": 999}, headers=admin).json()
    assert (body["price_cents"], body["name"]) == (999, "Unit Test Gadget")


@pytest.mark.feature("admin")
def test_admin_soft_delete_hides_product(client, admin):
    """A deleted product disappears from the catalog but still exists for admins."""
    pid = client.post("/admin/products", json=NEW_PRODUCT, headers=admin).json()["id"]
    assert client.delete(f"/admin/products/{pid}", headers=admin).status_code == 204
    assert client.get(f"/products/{pid}").status_code == 404
    all_products = client.get("/admin/products", headers=admin).json()
    assert any(p["id"] == pid and not p["is_active"] for p in all_products)


# ---------------- test support ----------------


@pytest.mark.feature("test-support")
@pytest.mark.parametrize("token", [None, "wrong"])
def test_reset_requires_token(client, token):
    """/test/reset refuses requests without the right X-Test-Token."""
    headers = {"X-Test-Token": token} if token else {}
    assert client.post("/test/reset", headers=headers).status_code == 401


@pytest.mark.feature("test-support")
def test_reset_restores_seed_state(client, admin):
    """After changes to users and products, reset brings back exactly the seed data."""
    client.post("/admin/products", json=NEW_PRODUCT, headers=admin)
    _register(client, email="temp@unit.test")

    response = client.post("/test/reset", headers={"X-Test-Token": UNIT_TEST_TOKEN})

    assert response.json() == {"status": "reset", "products": 49, "users": 2, "coupons": 5}
    assert client.get("/products").json()["total"] == 48


@pytest.mark.feature("test-support")
def test_bug_list_matches_registry(client):
    """/test/bugs lists all 11 switches."""
    response = client.get("/test/bugs", headers={"X-Test-Token": UNIT_TEST_TOKEN})
    assert len(response.json()) == 11
