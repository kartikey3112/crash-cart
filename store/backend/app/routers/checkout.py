"""DEMO checkout. The card form is fake: numbers are checked locally and nothing is charged."""

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bugs import Bug
from app.cart_logic import cart_totals, coupon_problem, load_cart_coupon, load_cart_items
from app.deps import api_error, bug_on, get_current_user, get_db
from app.models import CartCoupon, CartItem, Order, OrderItem, User, utcnow
from app.payments import card_expired, is_declined, luhn_valid, normalise_card_number
from app.schemas import CheckoutIn, ErrorResponse, OrderOut

router = APIRouter(tags=["checkout"])


def _existing_order(db: Session, user: User, key: str) -> Order | None:
    return db.scalar(select(Order).where(Order.user_id == user.id, Order.idempotency_key == key))


@router.post(
    "/checkout",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": OrderOut, "description": "Replay of an earlier request with the same key"},
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        402: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def checkout(
    body: CheckoutIn,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Order:
    """Place an order from the cart. Repeating a request with the same Idempotency-Key
    returns the original order (200) instead of creating a duplicate."""
    honour_key = idempotency_key is not None and not bug_on(request, Bug.CHECKOUT_DOUBLE_SUBMIT)
    if honour_key and (previous := _existing_order(db, user, idempotency_key)):
        response.status_code = status.HTTP_200_OK
        return previous

    now = utcnow()
    items = load_cart_items(db, user)
    if not items:
        raise api_error(status.HTTP_400_BAD_REQUEST, "cart_empty", "Cart is empty")

    coupon = load_cart_coupon(db, user)
    subtotal = sum(i.product.price_cents * i.quantity for i in items)
    ignore_expiry = bug_on(request, Bug.COUPON_EXPIRY_IGNORED)
    if coupon and (problem := coupon_problem(coupon, subtotal, now, ignore_expiry=ignore_expiry)):
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, *problem)

    if not bug_on(request, Bug.STOCK_NOT_ENFORCED):
        for item in items:
            if item.quantity > item.product.stock:
                raise api_error(
                    status.HTTP_409_CONFLICT,
                    "insufficient_stock",
                    f"Only {item.product.stock} of {item.product.sku} in stock",
                )

    card = body.card
    if not luhn_valid(card.number):
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "card_invalid", "Card number is invalid"
        )
    if not bug_on(request, Bug.EXPIRED_CARD_ACCEPTED) and card_expired(card.expiry, now.date()):
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "card_expired", "Card has expired")
    if is_declined(card.number):
        raise api_error(status.HTTP_402_PAYMENT_REQUIRED, "card_declined", "Card was declined")

    totals = cart_totals(request, items, coupon, now)
    ship = body.shipping
    order = Order(
        user_id=user.id,
        subtotal_cents=totals.subtotal_cents,
        discount_cents=totals.discount_cents,
        tax_cents=totals.tax_cents,
        shipping_cents=totals.shipping_cents,
        total_cents=totals.total_cents,
        coupon_code=coupon.code if coupon and totals.discount_cents else None,
        card_last4=normalise_card_number(card.number)[-4:],
        shipping_address=f"{ship.full_name}, {ship.address_line1}, {ship.city} "
        f"{ship.postal_code}, {ship.country}",
        idempotency_key=idempotency_key if honour_key else None,
        created_at=now,
        items=[
            OrderItem(
                product_id=i.product_id,
                product_name=i.product.name,
                unit_price_cents=i.product.price_cents,
                quantity=i.quantity,
                line_total_cents=i.product.price_cents * i.quantity,
            )
            for i in items
        ],
    )
    db.add(order)
    for item in items:
        item.product.stock = max(0, item.product.stock - item.quantity)
    if order.coupon_code:
        coupon.used_count += 1
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.execute(delete(CartCoupon).where(CartCoupon.user_id == user.id))

    try:
        db.commit()
    except IntegrityError:
        # Two requests with the same key raced; the other one won, so return its order.
        db.rollback()
        previous = _existing_order(db, user, idempotency_key) if honour_key else None
        if previous is None:
            raise
        response.status_code = status.HTTP_200_OK
        return previous
    return order
