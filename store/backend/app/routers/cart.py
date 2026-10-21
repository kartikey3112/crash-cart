from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bugs import Bug
from app.cart_logic import build_cart_out, coupon_problem, load_cart_items
from app.deps import api_error, bug_on, get_current_user, get_db
from app.models import CartCoupon, CartItem, Coupon, Product, User, utcnow
from app.schemas import CartItemIn, CartOut, CartQuantityIn, CouponIn, ErrorResponse

router = APIRouter(
    prefix="/cart",
    tags=["cart"],
    responses={401: {"model": ErrorResponse}},
)


def _check_stock(request: Request, product: Product, wanted: int) -> None:
    if bug_on(request, Bug.STOCK_NOT_ENFORCED):
        return
    if wanted > product.stock:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "insufficient_stock",
            f"Only {product.stock} of {product.sku} in stock",
        )


def _find_item(db: Session, user: User, product_id: int) -> CartItem:
    item = db.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id)
    )
    if item is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "item_not_in_cart", "Product is not in the cart")
    return item


@router.get("", response_model=CartOut)
def get_cart(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CartOut:
    """The current user's cart with server-calculated totals."""
    return build_cart_out(request, db, user, utcnow())


@router.post(
    "/items",
    response_model=CartOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def add_item(
    body: CartItemIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    """Add a product. Adding a product already in the cart increases its quantity."""
    product = db.get(Product, body.product_id)
    if product is None or not product.is_active:
        raise api_error(status.HTTP_404_NOT_FOUND, "product_not_found", "Product not found")

    existing = next((i for i in load_cart_items(db, user) if i.product_id == product.id), None)
    new_quantity = body.quantity + (existing.quantity if existing else 0)
    _check_stock(request, product, new_quantity)

    if existing:
        existing.quantity = new_quantity
    else:
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=new_quantity))
    db.commit()
    return build_cart_out(request, db, user, utcnow())


@router.patch(
    "/items/{product_id}",
    response_model=CartOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_item(
    product_id: int,
    body: CartQuantityIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    """Set the quantity of a product already in the cart."""
    item = _find_item(db, user, product_id)
    _check_stock(request, item.product, body.quantity)
    item.quantity = body.quantity
    db.commit()
    return build_cart_out(request, db, user, utcnow())


@router.delete(
    "/items/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def remove_item(
    product_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Remove a product from the cart."""
    item = _find_item(db, user, product_id)
    if not bug_on(request, Bug.REMOVE_ITEM_NOOP):
        db.delete(item)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/coupon",
    response_model=CartOut,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def apply_coupon(
    body: CouponIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    """Apply a coupon code (case-insensitive). Replaces any coupon already applied."""
    coupon = db.get(Coupon, body.code.strip().upper())
    if coupon is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "coupon_not_found", "Unknown coupon code")

    subtotal = sum(i.product.price_cents * i.quantity for i in load_cart_items(db, user))
    ignore_expiry = bug_on(request, Bug.COUPON_EXPIRY_IGNORED)
    problem = coupon_problem(coupon, subtotal, utcnow(), ignore_expiry=ignore_expiry)
    if problem:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, *problem)

    applied = db.get(CartCoupon, user.id)
    if applied:
        applied.coupon_code = coupon.code
    else:
        db.add(CartCoupon(user_id=user.id, coupon_code=coupon.code))
    db.commit()
    return build_cart_out(request, db, user, utcnow())


@router.delete("/coupon", status_code=status.HTTP_204_NO_CONTENT)
def remove_coupon(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Remove the applied coupon, if any. Safe to call repeatedly."""
    applied = db.get(CartCoupon, user.id)
    if applied:
        db.delete(applied)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
