"""FAKE card checks for the demo checkout. No card data leaves the server and nothing is charged."""

from datetime import date

APPROVED_TEST_CARD = "4242424242424242"
DECLINED_TEST_CARD = "4000000000000002"


def normalise_card_number(number: str) -> str:
    return number.replace(" ", "").replace("-", "")


def luhn_valid(number: str) -> bool:
    """Standard Luhn checksum: double every second digit from the right."""
    digits = normalise_card_number(number)
    if not digits.isdigit() or not 12 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def card_expired(expiry: str, today: date) -> bool:
    """expiry is "MM/YY" (format already validated). Valid through the end of that month."""
    month, year = int(expiry[:2]), 2000 + int(expiry[3:])
    return (year, month) < (today.year, today.month)


def is_declined(number: str) -> bool:
    return normalise_card_number(number) == DECLINED_TEST_CARD
