import { LAYER_LABELS, SYSTEM_LAYERS, el, fmtDate, loadJSON, renderShell, showError, statusBadge } from "./common.js";

renderShell("catalog.html");
const app = document.getElementById("app");

function latestStatuses(run) {
  const map = new Map();
  for (const t of run?.tests || []) {
    // UI tests are catalogued with their Chromium id; any browser's latest result counts.
    map.set(t.id.replace(/\[(firefox|webkit)\]$/, "[chromium]"), t.status);
  }
  return map;
}

function bugCoverage(tests) {
  const bugs = [...new Set(tests.flatMap((t) => t.bugs))].sort();
  return el("section", { class: "card section", "data-testid": "bug-coverage" },
    el("h2", {}, "Bug switches and the tests that target them"),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Bug switch"), SYSTEM_LAYERS.map((l) => el("th", { class: "num" }, `${LAYER_LABELS[l]} tests`)))),
      el("tbody", {}, bugs.map((bug) => el("tr", {},
        el("td", {}, el("span", { class: "pill bug" }, bug)),
        SYSTEM_LAYERS.map((layer) => el("td", { class: "num" }, tests.filter((t) => t.layer === layer && t.bugs.includes(bug)).length || "-"))))))));
}

function listView(tests, statuses, withLayer) {
  const features = [...new Set(tests.map((t) => t.feature))].sort();
  const bugs = [...new Set(tests.flatMap((t) => t.bugs))].sort();
  const state = { layer: "all", feature: "all", bug: "all", text: "" };
  const count = el("span", { class: "muted", "data-testid": "catalog-count" });
  const tbody = el("tbody");

  const apply = () => {
    const needle = state.text.toLowerCase();
    const shown = tests.filter((t) =>
      (state.layer === "all" || t.layer === state.layer) &&
      (state.feature === "all" || t.feature === state.feature) &&
      (state.bug === "all" || t.bugs.includes(state.bug)) &&
      (!needle || `${t.id} ${t.docstring}`.toLowerCase().includes(needle)));
    count.textContent = `${shown.length} of ${tests.length} tests`;
    tbody.replaceChildren(...(shown.length ? shown.map((t) => el("tr", { "data-testid": "catalog-row" },
      el("td", { class: "test-id" }, el("div", {}, t.name), el("div", { class: "doc" }, t.docstring), el("div", { class: "muted mono" }, t.file)),
      withLayer ? el("td", {}, LAYER_LABELS[t.layer]) : null,
      el("td", {}, t.feature),
      el("td", {}, t.bugs.map((b) => el("span", { class: "pill bug" }, b))),
      el("td", {}, statuses.has(t.id) ? statusBadge(statuses.get(t.id)) : el("span", { class: "muted" }, "not in latest run"))))
      : [el("tr", {}, el("td", { colspan: 5, class: "empty" }, "No tests match these filters."))]));
  };

  const select = (key, label, options) => el("label", {}, label,
    el("select", { "data-testid": `catalog-${key}`, onchange: (e) => { state[key] = e.target.value; apply(); } },
      el("option", { value: "all" }, `All ${label.toLowerCase()}s`), options.map(([v, text]) => el("option", { value: v }, text))));

  const controls = el("div", { class: "controls" },
    el("label", {}, "Search", el("input", { type: "search", placeholder: "name or what it checks", "data-testid": "catalog-search", oninput: (e) => { state.text = e.target.value; apply(); } })),
    withLayer ? select("layer", "Layer", SYSTEM_LAYERS.filter((l) => tests.some((t) => t.layer === l)).map((l) => [l, LAYER_LABELS[l]])) : null,
    select("feature", "Feature", features.map((f) => [f, f])),
    bugs.length ? select("bug", "Bug switch", bugs.map((b) => [b, b])) : null,
    count);
  apply();
  return el("div", {}, controls, el("div", { class: "card table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Test and what it checks", withLayer ? "Layer" : null, "Feature", "Targets bug", "Latest result"].filter(Boolean).map((h) => el("th", {}, h)))),
    tbody)));
}

async function main() {
  try {
    const [catalog, index] = await Promise.all([loadJSON("data/catalog.json"), loadJSON("data/runs/index.json")]);
    const latestRun = index.length ? await loadJSON(`data/runs/${encodeURIComponent(index[0].id)}.json`) : null;
    const statuses = latestStatuses(latestRun);
    const system = catalog.tests.filter((t) => t.layer !== "unit");
    const unit = catalog.tests.filter((t) => t.layer === "unit");

    const body = el("div");
    const tabs = [["system", `System tests (${system.length})`], ["unit", `Backend unit tests (${unit.length})`]];
    const buttons = tabs.map(([key, label]) => el("button", { type: "button", role: "tab", "data-testid": `catalog-tab-${key}`, onclick: () => show(key) }, label));
    function show(key) {
      buttons.forEach((b, i) => b.setAttribute("aria-selected", String(tabs[i][0] === key)));
      body.replaceChildren(key === "system"
        ? el("div", {}, listView(system, statuses, true), bugCoverage(system))
        : el("div", {}, el("p", { class: "ink-2" }, "In-process tests of the backend code (pricing, payments, bug-switch gating, every route). They run without a deployed store and are reported separately."),
          listView(unit, statuses, false)));
    }

    app.replaceChildren(
      el("h1", {}, "Test catalog"),
      el("p", { class: "ink-2" }, `Every test and the one sentence describing what it checks, generated from the test code's markers and docstrings. Updated ${fmtDate(catalog.generated_at)}.`),
      el("div", { class: "tabs", role: "tablist" }, buttons),
      body);
    show("system");
  } catch (error) {
    showError(app, error);
  }
}

main();
