"""Run configuration for the system tests, read from environment variables.

Defaults target a local stack with dev secrets: backend on :8000 and the frontend's
production build served by `vite preview` on :4173.
CI overrides every value from GitHub Secrets.
"""

import os
from dataclasses import dataclass

# Must match the backend's bug registry (store/backend/app/bugs.py). A test checks this.
KNOWN_BUGS = (
    "cart_rounding",
    "search_ignores_filters",
    "expired_card_accepted",
    "slow_products",
    "pagination_off_by_one",
    "coupon_expiry_ignored",
    "stock_not_enforced",
    "order_idor",
    "checkout_double_submit",
    "sort_desc_broken",
    "remove_item_noop",
)


@dataclass(frozen=True)
class RunConfig:
    api_base_url: str
    ui_base_url: str
    test_token: str
    admin_email: str
    admin_password: str
    wake_timeout_s: int
    reset_before_run: bool
    enabled_bugs: tuple[str, ...]  # bug switches turned on for EVERY request in this run

    @property
    def bug_headers(self) -> dict[str, str]:
        if not self.enabled_bugs:
            return {}
        return {"X-Bug-Switches": ",".join(self.enabled_bugs), "X-Test-Token": self.test_token}


def load_config() -> RunConfig:
    bugs = tuple(b.strip() for b in os.getenv("ENABLE_BUGS", "").split(",") if b.strip())
    return RunConfig(
        api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        ui_base_url=os.getenv("UI_BASE_URL", "http://localhost:4173").rstrip("/"),
        test_token=os.getenv("TEST_TOKEN", "dev-test-token"),
        admin_email=os.getenv("ADMIN_EMAIL", "admin@crashcart.test"),
        admin_password=os.getenv("ADMIN_PASSWORD", "admin-dev-password"),
        wake_timeout_s=int(os.getenv("WAKE_TIMEOUT_S", "120")),
        reset_before_run=os.getenv("RESET_BEFORE_RUN", "true").lower() == "true",
        enabled_bugs=bugs,
    )
