import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { Product } from "../api/types";
import { ErrorMessage, Loading } from "../components/common";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { formatCents } from "../utils/format";

export function ProductPage() {
  const { productId } = useParams();
  const { user } = useAuth();
  const { setCart } = useCart();
  const [product, setProduct] = useState<Product | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [quantity, setQuantity] = useState("1");
  const [addError, setAddError] = useState<string | null>(null);
  const [added, setAdded] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .product(Number(productId))
      .then(setProduct)
      .catch((err: unknown) =>
        setLoadError(err instanceof ApiError ? err.message : "Could not load product"),
      );
  }, [productId]);

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    if (!product) return;
    setAdded(false);
    setAddError(null);
    const qty = Number(quantity);
    if (!Number.isInteger(qty) || qty < 1) {
      setAddError("Quantity must be a whole number of at least 1");
      return;
    }
    setBusy(true);
    try {
      setCart(await api.addToCart(product.id, qty));
      setAdded(true);
    } catch (err) {
      setAddError(err instanceof ApiError ? err.message : "Could not add to cart");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} testId="product-error" />;
  if (!product) return <Loading testId="product-loading" />;

  return (
    <article className="product-detail" data-testid="product-detail" data-sku={product.sku}>
      <img src={product.image_path} alt="" className="product-image" data-testid="product-image" />
      <div className="product-info">
        <Link to={`/?category=${product.category.slug}`} className="product-category" data-testid="product-category">
          {product.category.name}
        </Link>
        <h1 data-testid="product-name">{product.name}</h1>
        <p className="product-price" data-testid="product-price">
          {formatCents(product.price_cents)}
        </p>
        <p className="product-sku">SKU {product.sku}</p>
        <p data-testid="product-stock" className={product.stock === 0 ? "out-of-stock" : "in-stock"}>
          {product.stock === 0 ? "Out of stock" : `${product.stock} in stock`}
        </p>
        <p className="product-description" data-testid="product-description">
          {product.description}
        </p>

        {user ? (
          <form className="add-to-cart" onSubmit={handleAdd} noValidate>
            <label className="field">
              <span>Quantity</span>
              <input
                type="number"
                min={1}
                max={99}
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                data-testid="quantity-input"
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={busy} data-testid="add-to-cart">
              Add to cart
            </button>
          </form>
        ) : (
          <p data-testid="login-to-buy">
            <Link to={`/login?next=/products/${product.id}`} data-testid="login-to-buy-link">
              Log in
            </Link>{" "}
            to add this to your cart.
          </p>
        )}
        {added && (
          <p className="alert alert-success" role="status" data-testid="add-to-cart-success">
            Added to your cart.{" "}
            <Link to="/cart" data-testid="view-cart-link">
              View cart
            </Link>
          </p>
        )}
        <ErrorMessage message={addError} testId="add-to-cart-error" />
      </div>
    </article>
  );
}
