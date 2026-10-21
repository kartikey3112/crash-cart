import base64
import json

import pytest

from tests.api.assertions import expect_error, expect_json, expect_status
from tests.api.data import PASSWORD, unique_email
from tests.api.schemas import Token, User

pytestmark = [pytest.mark.api, pytest.mark.feature("auth")]


def test_register_returns_customer_profile(anon):
    """Registering returns 201 with a customer profile that matches the contract (no password)."""
    email = unique_email()
    user = expect_json(anon.register(email, PASSWORD, "Asha Tester"), 201, User)
    assert (user.email, user.role, user.full_name) == (email, "customer", "Asha Tester")


def test_register_normalises_email_case(anon):
    """An email registered in mixed case is stored in lower case."""
    email = unique_email()
    user = expect_json(anon.register(email.upper(), PASSWORD), 201, User)
    assert user.email == email


def test_duplicate_email_is_409_case_insensitive(anon):
    """Registering the same email again, even in different case, is a 409 conflict."""
    email = unique_email()
    expect_status(anon.register(email, PASSWORD), 201)
    expect_error(anon.register(email.upper(), PASSWORD), 409, "email_taken")


@pytest.mark.parametrize(
    ("password", "status"),
    [("x" * 7, 422), ("x" * 8, 201), ("x" * 72, 201), ("x" * 73, 422), ("é" * 37, 422)],
    ids=["7-chars", "8-chars", "72-bytes", "73-bytes", "74-bytes-multibyte"],
)
def test_password_length_boundaries(anon, password, status):
    """Passwords must be 8+ characters and at most 72 bytes (bcrypt's limit)."""
    expect_status(anon.register(unique_email(), password), status)


@pytest.mark.parametrize("email", ["plainaddress", "a@b", "two words@example.test", ""])
def test_malformed_email_is_422(anon, email):
    """Obviously malformed email addresses are rejected at registration."""
    expect_status(anon.register(email, PASSWORD), 422)


@pytest.mark.parametrize(
    "missing", ["email", "password", "full_name"], ids=["no-email", "no-password", "no-name"]
)
def test_register_missing_field_is_422(anon, missing):
    """Each required registration field is really required."""
    body = {"email": unique_email(), "password": PASSWORD, "full_name": "X"}
    del body[missing]
    expect_status(anon.request("POST", "/auth/register", json=body), 422)


def test_login_returns_working_token(make_client):
    """A valid login returns a bearer token that /auth/me accepts."""
    client, email = make_client(), unique_email()
    client.register(email, PASSWORD)
    expect_json(client.login(email, PASSWORD), 200, Token)
    assert expect_json(client.me(), 200, User).email == email


@pytest.mark.parametrize("case", ["wrong-password", "unknown-email"])
def test_failed_login_does_not_reveal_which_part_was_wrong(anon, case):
    """Wrong password and unknown email both give the same 401 invalid_credentials."""
    email = unique_email()
    anon.register(email, PASSWORD)
    if case == "wrong-password":
        body = {"email": email, "password": "not-the-password"}
    else:
        body = {"email": unique_email(), "password": PASSWORD}
    response = anon.request("POST", "/auth/login", json=body)
    expect_error(response, 401, "invalid_credentials")


def test_me_requires_token(anon):
    """/auth/me without a token is 401 and advertises the Bearer scheme."""
    response = anon.request("GET", "/auth/me")
    expect_error(response, 401, "not_authenticated")
    assert response.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.parametrize(
    "token", ["not-a-jwt", "Bearer", "a.b.c"], ids=["garbage", "word", "fake-jwt"]
)
def test_me_rejects_garbage_token(anon, token):
    """Malformed bearer tokens are rejected with 401."""
    response = anon.request("GET", "/auth/me", headers={"Authorization": f"Bearer {token}"})
    expect_error(response, 401, "not_authenticated")


def test_me_rejects_tampered_token(customer):
    """Changing the token's payload (role -> admin) without re-signing it is rejected."""
    header, payload, signature = customer.token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["role"] = "admin"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    response = customer.request(
        "GET", "/auth/me", headers={"Authorization": f"Bearer {header}.{forged}.{signature}"}
    )
    expect_error(response, 401, "not_authenticated")


def test_logout_is_client_side(customer):
    """JWTs are stateless: once the client drops the token, protected calls are 401."""
    expect_status(customer.me(), 200)
    customer.token = None
    expect_status(customer.me(), 401)
