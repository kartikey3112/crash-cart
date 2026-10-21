import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { Category, ProductPage, SortOption } from "../api/types";
import { ErrorMessage, Loading } from "../components/common";
import { dollarsToCents, formatCents } from "../utils/format";

const SORT_LABELS: Record<SortOption, string> = {
  name: "Name (A–Z)",
  price_asc: "Price: low to high",
  price_desc: "Price: high to low",
  newest: "Newest",
};

const PAGE_SIZE = 12;

// Filters live in the URL so every result page is linkable and tests can open it directly.
export function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const sort = (params.get("sort") as SortOption | null) ?? "name";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const minPrice = params.get("min") ?? "";
  const maxPrice = params.get("max") ?? "";

  const [categories, setCategories] = useState<Category[]>([]);
  const [result, setResult] = useState<ProductPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Draft values for the filter form; applied to the URL on submit.
  const [draftQ, setDraftQ] = useState(q);
  const [draftMin, setDraftMin] = useState(minPrice);
  const [draftMax, setDraftMax] = useState(maxPrice);

  // Keep the form in step with the URL (e.g. after Back/Forward navigation).
  useEffect(() => {
    setDraftQ(q);
    setDraftMin(minPrice);
    setDraftMax(maxPrice);
  }, [q, minPrice, maxPrice]);

  useEffect(() => {
    api.categories().then(setCategories).catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .products({
        q: q || undefined,
        category: category || undefined,
        sort,
        page,
        page_size: PAGE_SIZE,
        min_price_cents: minPrice ? dollarsToCents(minPrice) : undefined,
        max_price_cents: maxPrice ? dollarsToCents(maxPrice) : undefined,
      })
      .then(setResult)
      .catch((err: unknown) => {
        setResult(null);
        setError(err instanceof ApiError ? err.message : "Could not load products");
      })
      .finally(() => setLoading(false));
  }, [q, category, sort, page, minPrice, maxPrice]);

  function updateParams(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    // Any filter change starts again from page 1, unless the change *is* the page.
    if (!("page" in changes)) next.delete("page");
    setParams(next);
  }

  function handleFilterSubmit(event: FormEvent) {
    event.preventDefault();
    for (const value of [draftMin, draftMax]) {
      if (value && Number.isNaN(dollarsToCents(value))) {
        setError("Prices must be amounts like 25 or 19.99");
        return;
      }
    }
    updateParams({ q: draftQ.trim(), min: draftMin.trim(), max: draftMax.trim() });
  }

  return (
    <section data-testid="catalog-page">
      <h1>Shop gadgets</h1>

      <form className="filters" onSubmit={handleFilterSubmit} noValidate data-testid="filter-form">
        <label className="field field-grow">
          <span>Search</span>
          <input
            type="search"
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="e.g. wireless"
            data-testid="search-input"
          />
        </label>
        <label className="field">
          <span>Min price ($)</span>
          <input
            inputMode="decimal"
            value={draftMin}
            onChange={(e) => setDraftMin(e.target.value)}
            data-testid="price-min"
          />
        </label>
        <label className="field">
          <span>Max price ($)</span>
          <input
            inputMode="decimal"
            value={draftMax}
            onChange={(e) => setDraftMax(e.target.value)}
            data-testid="price-max"
          />
        </label>
        <button type="submit" className="btn btn-primary" data-testid="search-submit">
          Search
        </button>
      </form>

      <div className="toolbar">
        <label className="field">
          <span>Category</span>
          <select
            value={category}
            onChange={(e) => updateParams({ category: e.target.value })}
            data-testid="category-select"
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Sort by</span>
          <select
            value={sort}
            onChange={(e) => updateParams({ sort: e.target.value })}
            data-testid="sort-select"
          >
            {Object.entries(SORT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {result && (
          <p className="results-count" data-testid="results-count">
            {result.total} {result.total === 1 ? "product" : "products"}
          </p>
        )}
      </div>

      <ErrorMessage message={error} testId="catalog-error" />
      {loading && <Loading testId="catalog-loading" />}

      {!loading && result && result.items.length === 0 && (
        <p className="empty" data-testid="empty-results">
          No products match your search.
        </p>
      )}

      {!loading && result && result.items.length > 0 && (
        <>
          <ul className="product-grid" data-testid="product-grid">
            {result.items.map((product) => (
              <li
                key={product.id}
                className="product-card"
                data-testid="product-card"
                data-sku={product.sku}
                data-product-id={product.id}
              >
                <Link to={`/products/${product.id}`} data-testid="product-card-link">
                  <img src={product.image_path} alt="" className="product-thumb" loading="lazy" />
                  <span className="product-card-category">{product.category.name}</span>
                  <span className="product-card-name" data-testid="product-card-name">
                    {product.name}
                  </span>
                </Link>
                <span className="product-card-price" data-testid="product-card-price">
                  {formatCents(product.price_cents)}
                </span>
                {product.stock === 0 && (
                  <span className="tag tag-muted" data-testid="product-card-out-of-stock">
                    Out of stock
                  </span>
                )}
              </li>
            ))}
          </ul>

          <nav className="pagination" aria-label="Pagination">
            <button
              type="button"
              className="btn btn-ghost"
              disabled={page <= 1}
              onClick={() => updateParams({ page: String(page - 1) })}
              data-testid="pagination-prev"
            >
              ← Previous
            </button>
            <span data-testid="pagination-status">
              Page {result.page} of {Math.max(result.total_pages, 1)}
            </span>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={page >= result.total_pages}
              onClick={() => updateParams({ page: String(page + 1) })}
              data-testid="pagination-next"
            >
              Next →
            </button>
          </nav>
        </>
      )}
    </section>
  );
}
