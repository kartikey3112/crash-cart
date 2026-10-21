from datetime import date

import pytest

from app.payments import card_expired, is_declined, luhn_valid

pytestmark = [pytest.mark.unit, pytest.mark.feature("checkout")]


@pytest.mark.parametrize(
    "number", ["4242424242424242", "4242 4242 4242 4242", "4000-0000-0000-0002", "5555555555554444"]
)
def test_luhn_accepts_valid_numbers(number):
    """Well-known test card numbers pass the Luhn check, with or without spaces/dashes."""
    assert luhn_valid(number)


@pytest.mark.parametrize(
    "number", ["4242424242424241", "1234", "abcdabcdabcdabcd", "42424242424242424242"]
)
def test_luhn_rejects_invalid_numbers(number):
    """Wrong checksum, too short, non-digits and too long are all rejected."""
    assert not luhn_valid(number)


@pytest.mark.parametrize(
    ("expiry", "expired"),
    [("10/26", False), ("11/26", False), ("09/26", True), ("12/25", True), ("01/27", False)],
)
def test_card_expiry_boundaries(expiry, expired):
    """On 21 Oct 2026 a card expiring 10/26 is still valid; 09/26 is expired."""
    assert card_expired(expiry, date(2026, 10, 21)) is expired


def test_declined_test_card():
    """Only the documented decline card number is declined."""
    assert is_declined("4000 0000 0000 0002")
    assert not is_declined("4242424242424242")
