// Shared helpers for every dashboard page: data loading, a tiny DOM builder (text only,
// never innerHTML, so test names and error messages can't inject markup), formatting,
// and the page header/footer.

export const REPO_URL = "https://github.com/kartikey3112/crash-cart";
export const SYSTEM_LAYERS = ["api", "ui", "perf"];
export const LAYER_LABELS = { api: "API", ui: "UI", perf: "Perf", unit: "Backend unit", "api-local": "API (in-runner)" };

const PAGES = [
  ["index.html", "Overview"],
  ["runs.html", "Run history"],
  ["catalog.html", "Test catalog"],
  ["flaky.html", "Flaky tests"],
  ["downloads.html", "Downloads"],
];

export async function loadJSON(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

/** el("a", {href: "x", class: "y"}, "text", childNode, ...) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function param(name) {
  return new URLSearchParams(location.search).get(name);
}

export function fmtDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function fmtShortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function fmtDuration(seconds) {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds - minutes * 60)} s`;
}

export function fmtBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function pct(value) {
  return value === null || value === undefined ? "-" : `${value}%`;
}

export function commitLink(sha) {
  const short = (sha || "").slice(0, 7) || "-";
  return sha && /^[0-9a-f]{7,40}$/.test(sha)
    ? el("a", { href: `${REPO_URL}/commit/${sha}`, class: "mono", target: "_blank", rel: "noopener" }, short)
    : el("span", { class: "mono" }, short);
}

export function statusBadge(status, big = false) {
  const labels = { passed: "Passed", failed: "Failed", error: "Error", skipped: "Skipped", flaky: "Flaky" };
  return el("span", { class: `status ${status}${big ? " big" : ""}`, "data-testid": "status" }, labels[status] || status);
}

export function runVerdict(summary) {
  const c = summary.counts;
  return c.failed + c.error > 0 ? "failed" : "passed";
}

export function bugPills(bugs) {
  return bugs.length
    ? bugs.map((bug) => el("span", { class: "pill bug", title: "Bug switch enabled for this run" }, bug))
    : [el("span", { class: "muted" }, "none")];
}

/** Totals over the system-test layers only (unit tests are reported separately). */
export function systemCounts(summary) {
  const total = { total: 0, passed: 0, failed: 0, error: 0, skipped: 0, flaky: 0 };
  for (const layer of SYSTEM_LAYERS) {
    const counts = summary.layers[layer];
    if (!counts) continue;
    for (const key of Object.keys(total)) total[key] += counts[key];
  }
  const executed = total.total - total.skipped;
  total.pass_rate = executed ? Math.round(((total.passed + total.flaky) / executed) * 1000) / 10 : null;
  return total;
}

export function renderShell(active) {
  const header = el(
    "header",
    { class: "site-header" },
    el(
      "div",
      { class: "container header-inner" },
      el(
        "a",
        { class: "brand", href: "index.html", "data-testid": "brand" },
        el("img", { src: "img/logo.svg", alt: "", width: 30, height: 30 }),
        "CrashCart ",
        el("small", {}, "test results"),
      ),
      el(
        "nav",
        { class: "nav", "aria-label": "Dashboard" },
        PAGES.map(([href, label]) =>
          el("a", { href, "aria-current": href === active ? "page" : null, "data-testid": `nav-${href.replace(".html", "")}` }, label),
        ),
      ),
    ),
  );
  const footer = el(
    "footer",
    { class: "site-footer" },
    el(
      "div",
      { class: "container" },
      "Every number here comes from real test runs against CrashCart, a fictional store built to be tested. ",
      el("a", { href: REPO_URL, target: "_blank", rel: "noopener" }, "Source on GitHub"),
    ),
  );
  document.body.prepend(header);
  document.body.append(footer);
}

export function showError(container, error) {
  container.replaceChildren(
    el("div", { class: "error-box", role: "alert", "data-testid": "load-error" }, `Could not load results: ${error.message}`),
  );
}
