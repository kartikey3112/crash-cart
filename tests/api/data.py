"""Test data rules.

Tests run in parallel against a shared store, so each test creates its own users, and
seeded products are assigned roles so tests can't disturb each other:

- GENERAL_ITEM: cheap, high stock (120). Any test may add or buy it.
- STOCK_DECREMENT_ITEM: bought ONLY by the stock-decrement test, so its count is predictable.
- LOW_STOCK_ITEM: stock 3, NEVER bought (only added to carts, which doesn't reserve stock).
- OUT_OF_STOCK_ITEM: stock 0.
- PREMIUM_ITEM: $49.99, used for coupon maths.

Admin tests create products only in the "gaming" category, priced $12.34, named
"API Test ...", and soft-delete them afterwards. Catalog tests avoid relying on those.
"""

import random
import string
import uuid

GENERAL_ITEM = "PHN-003"  # Braided USB-C Cable 2m, $9.99
STOCK_DECREMENT_ITEM = "PHN-006"  # Clear Phone Case, $7.99
LOW_STOCK_ITEM = "AUD-008"  # Vinyl-Style Retro Speaker, $54.99, stock 3
OUT_OF_STOCK_ITEM = "WEA-006"  # Smart Ring Gen 1
PREMIUM_ITEM = "AUD-001"  # Pulse Wireless Earbuds, $49.99

PASSWORD = "api-test-password"

APPROVED_CARD = {
    "number": "4242 4242 4242 4242",
    "expiry": "12/39",
    "cvv": "123",
    "name_on_card": "API Tester",
}
DECLINED_CARD_NUMBER = "4000 0000 0000 0002"
EXPIRED_EXPIRY = "01/21"

SHIPPING = {
    "full_name": "API Tester",
    "address_line1": "42 Test Lane",
    "city": "Pune",
    "postal_code": "411001",
    "country": "India",
}


def unique_email() -> str:
    return f"api-{uuid.uuid4().hex[:12]}@example.test"


def unique_sku() -> str:
    # Seeded SKUs never start with Z, so test SKUs can't collide with them.
    letters = "".join(random.choices(string.ascii_uppercase, k=2))
    return f"Z{letters}-{random.randint(0, 999):03d}"
