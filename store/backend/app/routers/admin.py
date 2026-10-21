from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.deps import api_error, get_db, require_admin
from app.models import CartItem, Category, Product
from app.schemas import AdminProductOut, ErrorResponse, ProductCreateIn, ProductUpdateIn

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


def _category(db: Session, slug: str) -> Category:
    category = db.scalar(select(Category).where(Category.slug == slug))
    if category is None:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_category", f"No category '{slug}'"
        )
    return category


def _product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise api_error(status.HTTP_404_NOT_FOUND, "product_not_found", "Product not found")
    return product


@router.get("/products", response_model=list[AdminProductOut])
def list_all_products(db: Session = Depends(get_db)) -> list[Product]:
    """Every product, including soft-deleted ones."""
    return list(db.scalars(select(Product).order_by(Product.id)))


@router.post(
    "/products",
    response_model=AdminProductOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_product(body: ProductCreateIn, db: Session = Depends(get_db)) -> Product:
    """Create a product."""
    if db.scalar(select(Product).where(Product.sku == body.sku)) is not None:
        raise api_error(status.HTTP_409_CONFLICT, "sku_taken", f"SKU {body.sku} already exists")
    product = Product(
        sku=body.sku,
        name=body.name,
        description=body.description,
        category=_category(db, body.category_slug),
        price_cents=body.price_cents,
        stock=body.stock,
        image_path=body.image_path,
    )
    db.add(product)
    db.commit()
    return product


@router.patch(
    "/products/{product_id}",
    response_model=AdminProductOut,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_product(
    product_id: int, body: ProductUpdateIn, db: Session = Depends(get_db)
) -> Product:
    """Change only the fields that were sent."""
    product = _product(db, product_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if (slug := changes.pop("category_slug", None)) is not None:
        product.category = _category(db, slug)
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> Response:
    """Soft delete: hide the product but keep it, because past orders still reference it."""
    product = _product(db, product_id)
    product.is_active = False
    db.execute(delete(CartItem).where(CartItem.product_id == product.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
