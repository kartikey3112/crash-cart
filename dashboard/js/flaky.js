import { LAYER_LABELS, commitLink, el, fmtDate, loadJSON, renderShell, showError } from "./common.js";

renderShell("flaky.html");
const app = document.getElementById("app");

const runs = (n) => `${n} run${n === 1 ? "" : "s"}`;
const runLinks = (ids) => ids.map((id) => el("a", { href: `run.html?id=${encodeURIComponent(id)}`, class: "pill mono" }, id));

function definitions(flaky) {
  return el("section", { class: "card" },
    el("h2", {}, "How flakiness is measured"),
    el("ul", { class: "ink-2" },
      el("li", {}, el("strong", {}, "Same-commit conflict: "), "the test passed in one run and failed in another on the same commit, so the code didn't change but the result did."),
      el("li", {}, el("strong", {}, "Passed on retry: "), "UI tests get one retry; a test that failed and then passed is counted as flaky, not passed."),
      el("li", {}, el("strong", {}, `${flaky.window_days}-day flip rate: `), "how often the result changed between consecutive runs (changes ÷ (runs − 1))."),
      el("li", {}, el("strong", {}, "Excluded: "), "runs with bug switches on, because their failures are deliberate.")),
    el("p", { class: "muted" },
      `Based on ${runs(flaky.runs_considered)} without injected bugs (${runs(flaky.runs_excluded_with_bugs)} with bug switches excluded)` +
      (flaky.generated_at ? `, up to ${fmtDate(flaky.generated_at)}.` : ".")));
}

async function main() {
  try {
    const flaky = await loadJSON("data/flaky.json");
    const content = flaky.tests.length
      ? el("div", { class: "card table-wrap section" }, el("table", { "data-testid": "flaky-table" },
        el("thead", {}, el("tr", {}, ["Test", "Layer", "Flip rate (30 d)", "Same-commit conflicts", "Passed on retry in"].map((h, i) => el("th", { class: i === 2 ? "num" : null }, h)))),
        el("tbody", {}, flaky.tests.map((t) => el("tr", { "data-testid": "flaky-row" },
          el("td", { class: "test-id" }, el("div", {}, t.name), el("div", { class: "muted mono" }, t.id)),
          el("td", {}, LAYER_LABELS[t.layer] || t.layer),
          el("td", { class: "num" }, `${Math.round(t.flip_rate_30d * 100)}% (${t.flips_30d} of ${Math.max(t.runs_30d - 1, 0)})`),
          el("td", {}, t.same_commit_conflicts.length
            ? t.same_commit_conflicts.map((c) => el("div", {}, commitLink(c.commit_sha), ": passed ", runLinks(c.passed_runs), " failed ", runLinks(c.failed_runs)))
            : el("span", { class: "muted" }, "none")),
          el("td", {}, t.retry_flaky_runs.length ? runLinks(t.retry_flaky_runs) : el("span", { class: "muted" }, "never")))))))
      : el("div", { class: "card empty section", "data-testid": "flaky-empty" },
        el("strong", {}, "No flaky tests detected."),
        el("div", {}, `No test changed result on the same commit or passed only on retry, across ${runs(flaky.runs_considered)} without injected bugs.`));
    app.replaceChildren(el("h1", {}, "Flaky tests"), el("p", { class: "ink-2" }, "Tests whose result changes when the code doesn't."), definitions(flaky), content);
  } catch (error) {
    showError(app, error);
  }
}

main();
