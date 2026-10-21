import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { AdminProduct, Category, ProductInput } from "../api/types";
import { ErrorMessage, Loading } from "../components/common";
import { dollarsToCents, formatCents } from "../utils/format";

interface FormState {
  sku: string;
  name: string;
  description: string;
  category_slug: string;
  price: string; // dollars, as typed
  stock: string;
}

const EMPTY_FORM: FormState = { sku: "", name: "", description: "", category_slug: "", price: "", stock: "" };

function toInput(form: FormState): ProductInput | string {
  const price_cents = dollarsToCents(form.price);
  const stock = Number(form.stock);
  if (!form.name.trim()) return "Name is required";
  if (!form.category_slug) return "Choose a category";
  if (Number.isNaN(price_cents)) return "Price must be an amount like 19.99";
  if (form.stock.trim() === "" || !Number.isInteger(stock)) return "Stock must be a whole number";
  return {
    sku: form.sku.trim().toUpperCase(),
    name: form.name.trim(),
    description: form.description,
    category_slug: form.category_slug,
    price_cents,
    stock,
  };
}

export function AdminPage() {
  const [products, setProducts] = useState<AdminProduct[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setProducts(await api.adminProducts());
  }, []);

  useEffect(() => {
    load().catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load products"));
    api.categories().then(setCategories).catch(() => setCategories([]));
  }, [load]);

  const onField = (field: keyof FormState) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  function startEdit(product: AdminProduct) {
    setEditingId(product.id);
    setError(null);
    setSuccess(null);
    setForm({
      sku: product.sku,
      name: product.name,
      description: product.description,
      category_slug: product.category.slug,
      price: (product.price_cents / 100).toFixed(2),
      stock: String(product.stock),
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    const input = toInput(form);
    if (typeof input === "string") {
      setError(input);
      return;
    }
    try {
      if (editingId === null) {
        const created = await api.adminCreateProduct(input);
        setSuccess(`Created ${created.sku}`);
      } else {
        // SKU is the product's identity, so it isn't sent when editing.
        const updated = await api.adminUpdateProduct(editingId, {
          name: input.name,
          description: input.description,
          category_slug: input.category_slug,
          price_cents: input.price_cents,
          stock: input.stock,
        });
        setSuccess(`Saved ${updated.sku}`);
      }
      setEditingId(null);
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save product");
    }
  }

  async function handleDelete(id: number) {
    setError(null);
    setSuccess(null);
    try {
      await api.adminDeleteProduct(id);
      setConfirmDeleteId(null);
      setSuccess("Product deleted");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete product");
    }
  }

  return (
    <section data-testid="admin-page">
      <h1>Manage products</h1>

      <form className="admin-form" onSubmit={handleSubmit} noValidate data-testid="admin-product-form">
        <h2>{editingId === null ? "Add a product" : `Edit ${form.sku}`}</h2>
        <div className="field-row">
          <label className="field">
            <span>SKU (e.g. GAM-101)</span>
            <input value={form.sku} onChange={onField("sku")} disabled={editingId !== null} data-testid="admin-sku" />
          </label>
          <label className="field field-grow">
            <span>Name</span>
            <input value={form.name} onChange={onField("name")} data-testid="admin-name" />
          </label>
        </div>
        <div className="field-row">
          <label className="field">
            <span>Category</span>
            <select value={form.category_slug} onChange={onField("category_slug")} data-testid="admin-category">
              <option value="">Choose…</option>
              {categories.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Price ($)</span>
            <input inputMode="decimal" value={form.price} onChange={onField("price")} data-testid="admin-price" />
          </label>
          <label className="field">
            <span>Stock</span>
            <input inputMode="numeric" value={form.stock} onChange={onField("stock")} data-testid="admin-stock" />
          </label>
        </div>
        <label className="field">
          <span>Description</span>
          <textarea rows={2} value={form.description} onChange={onField("description")} data-testid="admin-description" />
        </label>
        <ErrorMessage message={error} testId="admin-form-error" />
        {success && (
          <p className="alert alert-success" role="status" data-testid="admin-form-success">
            {success}
          </p>
        )}
        <div className="button-row">
          <button type="submit" className="btn btn-primary" data-testid="admin-submit">
            {editingId === null ? "Add product" : "Save changes"}
          </button>
          {editingId !== null && (
            <button type="button" className="btn btn-ghost" onClick={cancelEdit} data-testid="admin-cancel-edit">
              Cancel
            </button>
          )}
        </div>
      </form>

      {!products ? (
        <Loading testId="admin-loading" />
      ) : (
        <div className="table-scroll">
          <table className="table" data-testid="admin-product-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Category</th>
                <th>Price</th>
                <th>Stock</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} data-testid="admin-product-row" data-sku={p.sku} data-product-id={p.id}>
                  <td>{p.sku}</td>
                  <td data-testid="admin-row-name">{p.name}</td>
                  <td>{p.category.name}</td>
                  <td data-testid="admin-row-price">{formatCents(p.price_cents)}</td>
                  <td data-testid="admin-row-stock">{p.stock}</td>
                  <td>
                    <span className={p.is_active ? "tag" : "tag tag-muted"} data-testid="admin-row-status">
                      {p.is_active ? "Active" : "Deleted"}
                    </span>
                  </td>
                  <td className="actions">
                    {p.is_active &&
                      (confirmDeleteId === p.id ? (
                        <>
                          <button type="button" className="btn btn-danger btn-small" onClick={() => handleDelete(p.id)} data-testid="admin-delete-confirm">
                            Confirm delete
                          </button>
                          <button type="button" className="btn btn-ghost btn-small" onClick={() => setConfirmDeleteId(null)} data-testid="admin-delete-cancel">
                            Keep
                          </button>
                        </>
                      ) : (
                        <>
                          <button type="button" className="btn btn-ghost btn-small" onClick={() => startEdit(p)} data-testid="admin-edit">
                            Edit
                          </button>
                          <button type="button" className="btn btn-link btn-small" onClick={() => setConfirmDeleteId(p.id)} data-testid="admin-delete">
                            Delete
                          </button>
                        </>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
