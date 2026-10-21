import math
import time

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.bugs import Bug
from app.config import Settings
from app.deps import api_error, bug_on, get_db, get_settings
from app.models import Category, Product
from app.schemas import CategoryOut, ErrorResponse, ProductOut, ProductPage, SortOption

router = APIRouter(tags=["catalog"])

# Every sort ends with Product.id so equal values always come back in the same order.
SORT_COLUMNS = {
    "name": (Product.name.asc(), Product.id.asc()),
    "price_asc": (Product.price_cents.asc(), Product.id.asc()),
    "price_desc": (Product.price_cents.desc(), Product.id.asc()),
    "newest": (Product.created_at.desc(), Product.id.desc()),
}


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    """All product categories, alphabetically."""
    return list(db.scalars(select(Category).order_by(Category.name)))


@router.get("/products", response_model=ProductPage)
def list_products(
    request: Request,
    q: str | None = Query(default=None, max_length=100, description="Search name and description"),
    category: str | None = Query(default=None, description="Category slug"),
    min_price_cents: int | None = Query(default=None, ge=0),
    max_price_cents: int | None = Query(default=None, ge=0),
    sort: SortOption = "name",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProductPage:
    """Search, filter, sort and paginate active products."""
    if (
        min_price_cents is not None
        and max_price_cents is not None
        and min_price_cents > max_price_cents
    ):
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_price_range",
            "min_price_cents must not exceed max_price_cents",
        )
    if bug_on(request, Bug.SLOW_PRODUCTS):
        time.sleep(settings.slow_bug_delay_ms / 1000)

    query = select(Product).where(Product.is_active.is_(True))

    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))

    skip_filters = bool(q) and bug_on(request, Bug.SEARCH_IGNORES_FILTERS)
    if not skip_filters:
        if category:
            query = query.join(Category).where(Category.slug == category)
        if min_price_cents is not None:
            query = query.where(Product.price_cents >= min_price_cents)
        if max_price_cents is not None:
            query = query.where(Product.price_cents <= max_price_cents)

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    sort_key = sort
    if sort == "price_desc" and bug_on(request, Bug.SORT_DESC_BROKEN):
        sort_key = "price_asc"

    offset = (page - 1) * page_size
    if page > 1 and bug_on(request, Bug.PAGINATION_OFF_BY_ONE):
        offset -= 1

    items = db.scalars(query.order_by(*SORT_COLUMNS[sort_key]).offset(offset).limit(page_size))
    return ProductPage(
        items=[ProductOut.model_validate(p) for p in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size),
    )


@router.get(
    "/products/{product_id}", response_model=ProductOut, responses={404: {"model": ErrorResponse}}
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    """One active product by id."""
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise api_error(status.HTTP_404_NOT_FOUND, "product_not_found", "Product not found")
    return product
