"""Intentionally injectable bugs, enabled per request.

A request turns bugs on by sending BOTH headers:
    X-Bug-Switches: cart_rounding,order_idor
    X-Test-Token: <secret>
Without a valid token the switches header is ignored, so normal visitors always get the
correct store. Every bug is off by default.
"""

import secrets
from enum import StrEnum


class Bug(StrEnum):
    CART_ROUNDING = "cart_rounding"
    SEARCH_IGNORES_FILTERS = "search_ignores_filters"
    EXPIRED_CARD_ACCEPTED = "expired_card_accepted"
    SLOW_PRODUCTS = "slow_products"
    PAGINATION_OFF_BY_ONE = "pagination_off_by_one"
    COUPON_EXPIRY_IGNORED = "coupon_expiry_ignored"
    STOCK_NOT_ENFORCED = "stock_not_enforced"
    ORDER_IDOR = "order_idor"
    CHECKOUT_DOUBLE_SUBMIT = "checkout_double_submit"
    SORT_DESC_BROKEN = "sort_desc_broken"
    REMOVE_ITEM_NOOP = "remove_item_noop"


BUG_DESCRIPTIONS: dict[Bug, str] = {
    Bug.CART_ROUNDING: "Discount and tax are truncated instead of rounded half-up.",
    Bug.SEARCH_IGNORES_FILTERS: "Category and price filters are dropped when searching.",
    Bug.EXPIRED_CARD_ACCEPTED: "Checkout skips the card expiry-date check.",
    Bug.SLOW_PRODUCTS: "GET /products sleeps before responding.",
    Bug.PAGINATION_OFF_BY_ONE: "Page N+1 repeats the last product of page N.",
    Bug.COUPON_EXPIRY_IGNORED: "Expired coupons are accepted.",
    Bug.STOCK_NOT_ENFORCED: "Cart quantity may exceed available stock.",
    Bug.ORDER_IDOR: "GET /orders/{id} returns orders belonging to other users.",
    Bug.CHECKOUT_DOUBLE_SUBMIT: "Idempotency-Key is ignored, so retries create duplicate orders.",
    Bug.SORT_DESC_BROKEN: "sort=price_desc returns products in ascending price order.",
    Bug.REMOVE_ITEM_NOOP: "Removing a cart item returns 204 but leaves the item in the cart.",
}


class UnknownBugError(ValueError):
    pass


def token_matches(provided: str | None, expected: str) -> bool:
    # compare_digest takes the same time whether or not the strings match (no timing leak).
    return provided is not None and secrets.compare_digest(provided, expected)


def parse_bug_header(header: str | None, token: str | None, expected_token: str) -> frozenset[Bug]:
    """Return the bugs to enable for this request.

    Raises UnknownBugError for a typo in a switch name, but only when the token is valid,
    so a test can never silently run with a bug it thinks is on.
    """
    if not header or not token_matches(token, expected_token):
        return frozenset()
    names = {name.strip() for name in header.split(",") if name.strip()}
    unknown = sorted(names - {bug.value for bug in Bug})
    if unknown:
        raise UnknownBugError(f"Unknown bug switch(es): {', '.join(unknown)}")
    return frozenset(Bug(name) for name in names)
