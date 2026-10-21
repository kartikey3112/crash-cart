const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatCents(cents: number): string {
  return currency.format(cents / 100);
}

/** "12.50" -> 1250. Returns NaN for anything that isn't a plain non-negative amount. */
export function dollarsToCents(text: string): number {
  if (!/^\d+(\.\d{1,2})?$/.test(text.trim())) return Number.NaN;
  return Math.round(Number.parseFloat(text) * 100);
}

export function formatDate(iso: string): string {
  // The API sends naive UTC timestamps; append Z so the browser doesn't treat them as local time.
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}
