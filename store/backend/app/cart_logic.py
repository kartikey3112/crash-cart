"""Cart and coupon rules shared by the cart and checkout endpoints."""

from dataclasses import asdict
from datetime import datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bugs import Bug
from app.deps import bug_on
from app.models import CartCoupon, CartItem, Coupon, User
from app.pricing import Discount, Totals, compute_totals
from app.schemas import CartLineOut, CartOut, TotalsOut


def coupon_problem(
    coupon: Coupon, subtotal_cents: int, now: datetime, *, ignore_expiry: bool = False
) -> tuple[str, str] | None:
    """Return (error_code, message) if the coupon can't be used right now, else None."""
    if not ignore_expiry and coupon.expires_at < now:
        return "coupon_expired", "This coupon has expired"
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return "coupon_used_up", "This coupon has reached its usage limit"
    if subtotal_cents < coupon.min_subtotal_cents:
        return "coupon_min_subtotal", f"Subtotal must be at least {coupon.min_subtotal_cents} cents"
    return None


def load_cart_items(db: Session, user: User) -> list[CartItem]:
    return list(
        db.scalars(select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.id))
    )


def load_cart_coupon(db: Session, user: User) -> Coupon | None:
    applied = db.get(CartCoupon, user.id)
    return db.get(Coupon, applied.coupon_code) if applied else None


def cart_totals(
    request: Request, items: list[CartItem], coupon: Coupon | None, now: datetime
) -> Totals:
    lines = [(item.product.price_cents, item.quantity) for item in items]
    subtotal = sum(price * qty for price, qty in lines)
    discount = None
    ignore_expiry = bug_on(request, Bug.COUPON_EXPIRY_IGNORED)
    # A coupon that stopped qualifying (e.g. subtotal fell below the minimum) gives no discount.
    if coupon and coupon_problem(coupon, subtotal, now, ignore_expiry=ignore_expiry) is None:
        discount = Discount(coupon.kind, coupon.value)
    return compute_totals(lines, discount, truncate=bug_on(request, Bug.CART_ROUNDING))


def build_cart_out(request: Request, db: Session, user: User, now: datetime) -> CartOut:
    items = load_cart_items(db, user)
    coupon = load_cart_coupon(db, user)
    totals = cart_totals(request, items, coupon, now)
    return CartOut(
        items=[
            CartLineOut(
                product_id=item.product_id,
                sku=item.product.sku,
                name=item.product.name,
                image_path=item.product.image_path,
                unit_price_cents=item.product.price_cents,
                quantity=item.quantity,
                line_total_cents=item.product.price_cents * item.quantity,
                stock=item.product.stock,
            )
            for item in items
        ],
        coupon_code=coupon.code if coupon else None,
        totals=TotalsOut(**asdict(totals)),
    )
