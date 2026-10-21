from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bugs import Bug
from app.deps import api_error, bug_on, get_current_user, get_db
from app.models import Order, User
from app.schemas import ErrorResponse, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"], responses={401: {"model": ErrorResponse}})


@router.get("", response_model=list[OrderOut])
def list_orders(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Order]:
    """The current user's orders, newest first."""
    query = select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())
    return list(db.scalars(query))


@router.get("/{order_id}", response_model=OrderOut, responses={404: {"model": ErrorResponse}})
def get_order(
    order_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Order:
    """One of the current user's orders. Other users' orders return 404, not 403,
    so the API doesn't reveal which order ids exist."""
    order = db.get(Order, order_id)
    owned = order is not None and order.user_id == user.id
    if order is None or not (owned or bug_on(request, Bug.ORDER_IDOR)):
        raise api_error(status.HTTP_404_NOT_FOUND, "order_not_found", "Order not found")
    return order
