"""Request and response models. These also drive the OpenAPI spec."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Deliberately simple email check, to avoid an extra dependency (email-validator).
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Cents = Annotated[int, Field(ge=0)]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail


# ---------- health / test support ----------


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str
    database: Literal["ok"]
    commit: str  # deployed git commit, or "unknown" locally


class ResetOut(BaseModel):
    status: Literal["reset"]
    products: int
    users: int
    coupons: int


class BugSwitchOut(BaseModel):
    name: str
    description: str


# ---------- auth ----------


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def _bcrypt_byte_limit(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes, and bcrypt 5 raises above that.
        if len(value.encode()) > 72:
            raise ValueError("password must be at most 72 bytes")
        return value


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Literal["customer", "admin"]
    created_at: datetime


# ---------- catalog ----------


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str
    category: CategoryOut
    price_cents: Cents
    stock: int
    image_path: str
    created_at: datetime


class AdminProductOut(ProductOut):
    is_active: bool
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductOut]
    page: int
    page_size: int
    total: int
    total_pages: int


SortOption = Literal["name", "price_asc", "price_desc", "newest"]


# ---------- cart ----------


class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class CartQuantityIn(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CouponIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)


class TotalsOut(BaseModel):
    subtotal_cents: Cents
    discount_cents: Cents
    tax_cents: Cents
    shipping_cents: Cents
    total_cents: Cents


class CartLineOut(BaseModel):
    product_id: int
    sku: str
    name: str
    image_path: str
    unit_price_cents: Cents
    quantity: int
    line_total_cents: Cents
    stock: int


class CartOut(BaseModel):
    items: list[CartLineOut]
    coupon_code: str | None
    totals: TotalsOut


# ---------- checkout / orders ----------


class ShippingIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    address_line1: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=3, max_length=12)
    country: str = Field(min_length=2, max_length=60)


class CardIn(BaseModel):
    number: str = Field(min_length=12, max_length=23)
    expiry: str = Field(pattern=r"^(0[1-9]|1[0-2])/\d{2}$", description="MM/YY")
    cvv: str = Field(pattern=r"^\d{3}$")
    name_on_card: str = Field(min_length=1, max_length=100)


class CheckoutIn(BaseModel):
    shipping: ShippingIn
    card: CardIn


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    unit_price_cents: Cents
    quantity: int
    line_total_cents: Cents


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    items: list[OrderItemOut]
    subtotal_cents: Cents
    discount_cents: Cents
    tax_cents: Cents
    shipping_cents: Cents
    total_cents: Cents
    coupon_code: str | None
    card_last4: str
    shipping_address: str
    created_at: datetime


# ---------- admin ----------


class ProductCreateIn(BaseModel):
    sku: str = Field(pattern=r"^[A-Z]{3}-\d{3}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    category_slug: str
    price_cents: int = Field(gt=0, le=1_000_000)
    stock: int = Field(ge=0, le=100_000)
    image_path: str = Field(default="/img/products/placeholder.svg", max_length=200)


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    category_slug: str | None = None
    price_cents: int | None = Field(default=None, gt=0, le=1_000_000)
    stock: int | None = Field(default=None, ge=0, le=100_000)
    image_path: str | None = Field(default=None, max_length=200)
