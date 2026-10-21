import {
  LAYER_LABELS, SYSTEM_LAYERS, bugPills, commitLink, el, fmtBytes, fmtDate, fmtDuration, loadJSON, param, pct,
  renderShell, runVerdict, showError, statusBadge, systemCounts,
} from "./common.js";

renderShell("runs.html");
const app = document.getElementById("app");
const STATUS_ORDER = { failed: 0, error: 0, flaky: 1, skipped: 2, passed: 3 };

// Playwright stores a retry's files in a folder ending "-retry1", "-retry2", ...
function attemptOf(path) {
  const match = /-retry(\d+)\//.exec(path);
  return match ? Number(match[1]) + 1 : 1;
}

function artifactLinks(test) {
  return test.artifacts.map((a) => {
    const attempt = test.attempts > 1 ? ` ${attemptOf(a.path)}` : "";
    if (a.type === "trace") {
      const absolute = new URL(a.path, location.href).href;
      return el("span", {},
        el("a", { href: a.path, class: "pill", download: "" }, `trace${attempt}`),
        el("a", { href: `https://trace.playwright.dev/?trace=${encodeURIComponent(absolute)}`, class: "pill", target: "_blank", rel: "noopener" }, `open in Trace Viewer${attempt}`));
    }
    return el("a", { href: a.path, class: "pill", target: "_blank", rel: "noopener" }, `screenshot${attempt}`);
  });
}

function testRow(test) {
  return el("tr", { "data-testid": "test-row", dataset: { status: test.status } },
    el("td", {}, statusBadge(test.status)),
    el("td", { class: "test-id" },
      el("div", {}, test.name),
      el("div", { class: "muted mono" }, test.id),
      test.message ? el("div", { class: "message" }, test.message) : null,
      test.artifacts.length ? el("div", {}, artifactLinks(test)) : null),
    el("td", {}, test.feature),
    el("td", {}, test.bugs.map((b) => el("span", { class: "pill bug" }, b))),
    el("td", { class: "num" }, `${test.duration_s.toFixed(2)} s`),
    el("td", { class: "num" }, test.attempts));
}

function testTable(tests) {
  const sorted = [...tests].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || a.id.localeCompare(b.id));
  return el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Status", "Test", "Feature", "Targets bug", "Duration", "Attempts"]
      .map((h, i) => el("th", { class: i >= 4 ? "num" : null }, h)))),
    el("tbody", {}, sorted.length ? sorted.map(testRow) : el("tr", {}, el("td", { colspan: 6, class: "empty" }, "No tests match.")))));
}

function filteredView(tests, initialStatus) {
  const state = { status: initialStatus || "all", text: "" };
  const holder = el("div");
  const apply = () => {
    const needle = state.text.toLowerCase();
    holder.replaceChildren(testTable(tests.filter((t) =>
      (state.status === "all" || t.status === state.status || (state.status === "failed" && t.status === "error")) &&
      (!needle || `${t.id} ${t.feature} ${t.bugs.join(" ")}`.toLowerCase().includes(needle)))));
  };
  const controls = el("div", { class: "controls" },
    el("label", {}, "Status", el("select", { "data-testid": "status-filter", onchange: (e) => { state.status = e.target.value; apply(); } },
      ["all", "failed", "flaky", "skipped", "passed"].map((s) => el("option", { value: s, selected: s === state.status }, s === "all" ? "All statuses" : s)))),
    el("label", {}, "Search", el("input", { type: "search", placeholder: "test name, feature or bug", "data-testid": "test-search", oninput: (e) => { state.text = e.target.value; apply(); } })));
  apply();
  return el("div", {}, controls, holder);
}

function header(run) {
  const downloads = Object.entries(run.reports).map(([kind, file]) =>
    el("a", { href: file.path, class: "pill", download: "" }, `${kind.toUpperCase()} · ${fmtBytes(file.bytes)}`));
  return el("section", { class: "card" },
    el("div", { class: "section-head" },
      el("div", {}, el("h1", {}, "Run detail"), el("div", { class: "mono muted" }, run.id)),
      statusBadge(runVerdict(run), true)),
    el("dl", { class: "kv" },
      el("dt", {}, "When"), el("dd", {}, fmtDate(run.timestamp)),
      el("dt", {}, "Commit"), el("dd", {}, commitLink(run.commit_sha), ` on ${run.branch}`),
      el("dt", {}, "Trigger"), el("dd", {}, run.trigger, run.workflow_url ? [" · ", el("a", { href: run.workflow_url, target: "_blank", rel: "noopener" }, "workflow run")] : null),
      el("dt", {}, "Bug switches"), el("dd", {}, bugPills(run.enabled_bugs)),
      el("dt", {}, "Duration"), el("dd", {}, fmtDuration(run.duration_s)),
      el("dt", {}, "Downloads"), el("dd", {}, downloads.length ? downloads : el("span", { class: "muted" }, "expired (older than the newest 30 runs)"))),
    run.enabled_bugs.length ? el("p", { class: "notice" }, "This run had bug switches on, so some failures are expected: they show the tests catching the injected bugs.") : null);
}

function layerTiles(run) {
  const c = systemCounts(run);
  return el("div", { class: "tiles" },
    el("div", { class: "card tile" }, el("div", { class: "label" }, "System tests"), el("div", { class: "value" }, pct(c.pass_rate)),
      el("div", { class: "sub" }, `${c.passed + c.flaky} of ${c.total - c.skipped} passed`)),
    SYSTEM_LAYERS.filter((l) => run.layers[l]).map((layer) => {
      const lc = run.layers[layer];
      return el("div", { class: "card tile", "data-testid": `layer-${layer}` }, el("div", { class: "label" }, LAYER_LABELS[layer]),
        el("div", { class: "value" }, `${lc.passed + lc.flaky}/${lc.total - lc.skipped}`),
        el("div", { class: "sub" }, `${lc.failed + lc.error} failed · ${lc.flaky} flaky · ${lc.skipped} skipped`));
    }));
}

function systemSection(run) {
  const layers = SYSTEM_LAYERS.filter((l) => run.layers[l]);
  if (!layers.length) return null;
  const initial = param("status");
  const body = el("div");
  const buttons = [];
  const select = (layer) => {
    buttons.forEach((b) => b.setAttribute("aria-selected", String(b.dataset.layer === layer)));
    const tests = layer === "all" ? run.tests.filter((t) => t.layer !== "unit") : run.tests.filter((t) => t.layer === layer);
    body.replaceChildren(filteredView(tests, initial));
  };
  for (const layer of ["all", ...layers]) {
    buttons.push(el("button", { type: "button", role: "tab", dataset: { layer }, "data-testid": `tab-${layer}`, onclick: () => select(layer) },
      layer === "all" ? "All system tests" : LAYER_LABELS[layer]));
  }
  const section = el("section", { class: "card section", "data-testid": "system-tests" },
    el("h2", {}, "System tests"), el("div", { class: "tabs", role: "tablist" }, buttons), body);
  select("all");
  return section;
}

function perfSection(run) {
  if (!run.perf.length) return null;
  return el("section", { class: "card section", "data-testid": "perf-table" },
    el("h2", {}, "Performance scenarios"),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Scenario", "Endpoint", "Users × s", "Samples", "Errors", "p50 ms", "p95 ms", "p99 ms", "Budget ms", "Result"]
        .map((h, i) => el("th", { class: i >= 2 && i <= 8 ? "num" : null }, h)))),
      el("tbody", {}, run.perf.map((p) => el("tr", {},
        el("td", {}, p.scenario), el("td", { class: "mono" }, p.path),
        el("td", { class: "num" }, `${p.profile.threads} × ${p.profile.duration_s}`),
        el("td", { class: "num" }, p.samples), el("td", { class: "num" }, p.errors),
        el("td", { class: "num" }, p.p50_ms), el("td", { class: "num" }, p.p95_ms), el("td", { class: "num" }, p.p99_ms),
        el("td", { class: "num" }, p.p95_budget_ms), el("td", {}, statusBadge(p.passed ? "passed" : "failed"))))))));
}

function unitSection(run) {
  const tests = run.tests.filter((t) => t.layer === "unit");
  if (!tests.length) return null;
  const c = run.layers.unit;
  const cov = run.coverage;
  return el("section", { class: "separate", "data-testid": "unit-tests" },
    el("div", { class: "section-head" },
      el("h2", {}, "Backend unit tests"),
      el("span", { class: "muted" }, "In-process tests of the FastAPI backend, kept separate from the system tests above")),
    el("div", { class: "tiles" },
      el("div", { class: "card tile" }, el("div", { class: "label" }, "Unit tests passed"), el("div", { class: "value" }, `${c.passed}/${c.total}`),
        el("div", { class: "sub" }, `${c.failed + c.error} failed · ${c.skipped} skipped`)),
      cov ? el("div", { class: "card tile", "data-testid": "coverage" }, el("div", { class: "label" }, "Backend coverage"), el("div", { class: "value" }, pct(cov.percent)),
        el("div", { class: "sub" }, `${cov.lines_covered}/${cov.lines_total} lines · ${cov.branches_covered}/${cov.branches_total} branches`)) : null),
    // A ?status= filter only applies here if some unit test actually has that status.
    el("div", { class: "card" }, filteredView(tests, tests.some((t) => t.status === param("status")) ? param("status") : "all")));
}

async function main() {
  const id = param("id");
  if (!id) {
    app.replaceChildren(el("div", { class: "card empty" }, "No run selected. ", el("a", { href: "runs.html" }, "Pick one from the run history.")));
    return;
  }
  try {
    const run = await loadJSON(`data/runs/${encodeURIComponent(id)}.json`);
    document.title = `Run ${run.id} · CrashCart test results`;
    app.replaceChildren(header(run), layerTiles(run));
    for (const section of [systemSection(run), perfSection(run), unitSection(run)]) {
      if (section) app.append(section);
    }
  } catch (error) {
    showError(app, error);
  }
}

main();
