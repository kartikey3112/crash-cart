"""Response contracts, written from the API's point of view (NOT imported from the backend,
so a backend change can't silently change the oracle). extra="forbid" makes any new,
renamed or leaked field (e.g. a password hash) fail validation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)


class Health(Contract):
    status: Literal["ok"]
    version: str
    database: Literal["ok"]
    commit: str = Field(min_length=1)


class ErrorDetail(Contract):
    code: str
    message: str


class ErrorBody(Contract):
    detail: ErrorDetail


class User(Contract):
    id: int
    email: str
    full_name: str
    role: Literal["customer", "admin"]
    created_at: datetime


class Token(Contract):
    access_token: str = Field(min_length=20)
    token_type: Literal["bearer"]
    expires_in: int = Field(gt=0)


class Category(Contract):
    id: int
    name: str
    slug: str


class Product(Contract):
    id: int
    sku: str = Field(pattern=r"^[A-Z]{3}-\d{3}$")
    name: str
    description: str
    category: Category
    price_cents: int = Field(gt=0)
    stock: NonNegativeInt
    image_path: str
    created_at: datetime


class AdminProduct(Product):
    is_active: bool
    updated_at: datetime


class ProductPage(Contract):
    items: list[Product]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total: NonNegativeInt
    total_pages: NonNegativeInt


class Totals(Contract):
    subtotal_cents: NonNegativeInt
    discount_cents: NonNegativeInt
    tax_cents: NonNegativeInt
    shipping_cents: NonNegativeInt
    total_cents: NonNegativeInt


class CartLine(Contract):
    product_id: int
    sku: str
    name: str
    image_path: str
    unit_price_cents: NonNegativeInt
    quantity: int = Field(ge=1)
    line_total_cents: NonNegativeInt
    stock: NonNegativeInt


class Cart(Contract):
    items: list[CartLine]
    coupon_code: str | None
    totals: Totals


class OrderItem(Contract):
    product_id: int
    product_name: str
    unit_price_cents: NonNegativeInt
    quantity: int = Field(ge=1)
    line_total_cents: NonNegativeInt


class Order(Contract):
    id: int
    status: str
    items: list[OrderItem] = Field(min_length=1)
    subtotal_cents: NonNegativeInt
    discount_cents: NonNegativeInt
    tax_cents: NonNegativeInt
    shipping_cents: NonNegativeInt
    total_cents: NonNegativeInt
    coupon_code: str | None
    card_last4: str = Field(pattern=r"^\d{4}$")
    shipping_address: str
    created_at: datetime
