import {
  LAYER_LABELS, bugPills, commitLink, el, fmtDate, fmtDuration, loadJSON, pct, renderShell, runVerdict,
  showError, statusBadge, systemCounts,
} from "./common.js";

renderShell("runs.html");
const app = document.getElementById("app");

function layerCell(summary) {
  return Object.entries(summary.layers).map(([layer, c]) =>
    el("span", { class: "pill", title: `${c.passed} passed, ${c.failed + c.error} failed, ${c.flaky} flaky` },
      `${LAYER_LABELS[layer]} ${c.passed + c.flaky}/${c.total - c.skipped}`));
}

function render(index, filters, tbody, countLabel) {
  const rows = index.filter((r) =>
    (filters.kind === "all" || (filters.kind === "clean") === (r.enabled_bugs.length === 0)) &&
    (filters.trigger === "all" || r.trigger === filters.trigger) &&
    (filters.result === "all" || runVerdict(r) === filters.result));
  countLabel.textContent = `${rows.length} of ${index.length} runs`;
  tbody.replaceChildren(...(rows.length ? rows.map((r) => el("tr", { "data-testid": "run-row", dataset: { runId: r.id } },
    el("td", {}, statusBadge(runVerdict(r))),
    el("td", {}, el("a", { href: `run.html?id=${encodeURIComponent(r.id)}` }, fmtDate(r.timestamp)), el("div", { class: "muted mono" }, r.id)),
    el("td", {}, r.trigger),
    el("td", {}, commitLink(r.commit_sha)),
    el("td", {}, bugPills(r.enabled_bugs)),
    el("td", {}, layerCell(r)),
    el("td", { class: "num" }, pct(systemCounts(r).pass_rate)),
    el("td", { class: "num" }, fmtDuration(r.duration_s)),
    el("td", {}, Object.keys(r.reports).length ? el("a", { href: "downloads.html#" + encodeURIComponent(r.id) }, "available") : el("span", { class: "muted" }, "summary only"))))
    : [el("tr", {}, el("td", { colspan: 9, class: "empty" }, "No runs match these filters."))]));
}

async function main() {
  try {
    const index = await loadJSON("data/runs/index.json");
    const filters = { kind: "all", trigger: "all", result: "all" };
    const tbody = el("tbody");
    const countLabel = el("span", { class: "muted", "data-testid": "run-count" });
    const select = (name, label, options) => el("label", {}, label,
      el("select", { "data-testid": `filter-${name}`, onchange: (e) => { filters[name] = e.target.value; render(index, filters, tbody, countLabel); } },
        options.map(([value, text]) => el("option", { value }, text))));
    const triggers = [...new Set(index.map((r) => r.trigger))].sort();

    app.replaceChildren(
      el("h1", {}, "Run history"),
      el("p", { class: "ink-2" }, "Every run, newest first. Runs with bug switches on fail on purpose: they prove the tests catch each injected bug."),
      el("div", { class: "controls" },
        select("kind", "Runs", [["all", "All runs"], ["clean", "No bugs injected"], ["bugs", "With bug switches on"]]),
        select("trigger", "Trigger", [["all", "Any trigger"], ...triggers.map((t) => [t, t])]),
        select("result", "Result", [["all", "Any result"], ["passed", "Passed"], ["failed", "Failed"]]),
        countLabel),
      el("div", { class: "card table-wrap" }, el("table", { "data-testid": "runs-table" },
        el("thead", {}, el("tr", {}, ["Result", "When", "Trigger", "Commit", "Bug switches", "Layers (passed/run)", "Pass rate", "Duration", "Reports"]
          .map((h, i) => el("th", { class: i === 6 || i === 7 ? "num" : null }, h)))),
        tbody)),
      el("p", { class: "muted" }, "Pass rate covers system tests (API, UI, perf). Full reports are kept for the newest 30 runs; older runs keep their results summary."),
    );
    render(index, filters, tbody, countLabel);
  } catch (error) {
    showError(app, error);
  }
}

main();
