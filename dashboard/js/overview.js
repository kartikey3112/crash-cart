import { durationChart, legend, onThemeChange, palette, passRateChart } from "./charts.js";
import {
  LAYER_LABELS, SYSTEM_LAYERS, bugPills, commitLink, el, fmtBytes, fmtDate, fmtDuration, fmtShortDate, loadJSON, pct,
  renderShell, runVerdict, showError, statusBadge, systemCounts,
} from "./common.js";

const TREND_RUNS = 30;
const SUITES = [
  { key: "unit", label: "Backend unit" },
  { key: "api", label: "API" },
  { key: "ui", label: "UI" },
  { key: "perf", label: "Perf" },
  { key: "api-local", label: "API (in-runner)" },  // added last so the other colours never move
];

renderShell("index.html");
const app = document.getElementById("app");

function tile(label, value, sub, testId) {
  return el("div", { class: "card tile", "data-testid": testId },
    el("div", { class: "label" }, label), el("div", { class: "value" }, value), el("div", { class: "sub" }, sub));
}

function suiteSeconds(summary) {
  // "ui-chromium" / "ui-firefox" etc. all count as the UI suite.
  const seconds = {};
  for (const [name, value] of Object.entries(summary.suite_seconds || {})) {
    const key = name.startsWith("ui") ? "ui" : name;
    seconds[key] = Math.round(((seconds[key] || 0) + value) * 10) / 10;
  }
  return seconds;
}

function latestCard(latest) {
  const c = systemCounts(latest);
  const downloads = Object.entries(latest.reports).map(([kind, file]) =>
    el("a", { href: file.path, class: "pill", download: "" }, `${kind.toUpperCase()} · ${fmtBytes(file.bytes)}`));
  return el("section", { class: "card", "data-testid": "latest-run" },
    el("div", { class: "section-head" },
      el("h2", {}, "Latest run"),
      el("a", { href: `run.html?id=${encodeURIComponent(latest.id)}` }, "Open run details →")),
    el("div", { class: "grid grid-2" },
      el("div", {},
        statusBadge(runVerdict(latest), true),
        el("div", { class: "hero", style: "margin-top:0.6rem" }, pct(c.pass_rate)),
        el("div", { class: "ink-2" }, `of ${c.total - c.skipped} system tests passed (API, UI, perf)`)),
      el("dl", { class: "kv" },
        el("dt", {}, "Run"), el("dd", { class: "mono" }, latest.id),
        el("dt", {}, "When"), el("dd", {}, fmtDate(latest.timestamp)),
        el("dt", {}, "Commit"), el("dd", {}, commitLink(latest.commit_sha), ` on ${latest.branch}`),
        el("dt", {}, "Trigger"), el("dd", {}, latest.trigger),
        el("dt", {}, "Bug switches"), el("dd", {}, bugPills(latest.enabled_bugs)),
        el("dt", {}, "Duration"), el("dd", {}, fmtDuration(latest.duration_s)),
        el("dt", {}, "Downloads"), el("dd", {}, downloads.length ? downloads : el("span", { class: "muted" }, "expired")))));
}

function tiles(latest, index) {
  const c = systemCounts(latest);
  const unit = latest.layers.unit;
  const local = latest.layers["api-local"];
  const withCoverage = index.find((r) => r.coverage);
  const withPerf = index.find((r) => r.perf && r.perf.length);
  const perfOk = withPerf ? withPerf.perf.filter((p) => p.passed).length : 0;
  const worst = withPerf ? withPerf.perf.reduce((a, b) => (b.p95_ms / b.p95_budget_ms > a.p95_ms / a.p95_budget_ms ? b : a)) : null;
  return el("div", { class: "tiles" },
    tile("System tests passed", `${c.passed + c.flaky} / ${c.total - c.skipped}`,
      `${c.failed + c.error} failed · ${c.flaky} flaky · ${c.skipped} skipped`, "tile-system"),
    ...["api", "ui", "perf"].filter((l) => latest.layers[l]).map((layer) => {
      const lc = latest.layers[layer];
      return tile(`${LAYER_LABELS[layer]} tests`, pct(lc.pass_rate), `${lc.passed + lc.flaky} of ${lc.total - lc.skipped} passed`, `tile-${layer}`);
    }),
    tile("Backend unit tests", unit ? `${unit.passed} / ${unit.total}` : "-",
      unit ? "reported separately from system tests" : "not run in this run", "tile-unit"),
    local ? tile("API (in-runner backend)", `${local.passed + local.flaky} / ${local.total - local.skipped}`,
      "CI self-test, not counted above", "tile-api-local") : null,
    tile("Backend coverage", withCoverage ? pct(withCoverage.coverage.percent) : "-",
      withCoverage ? `${withCoverage.coverage.lines_covered}/${withCoverage.coverage.lines_total} lines` : "no coverage data", "tile-coverage"),
    tile("Perf within p95 budget", withPerf ? `${perfOk} / ${withPerf.perf.length}` : "-",
      worst ? `slowest: ${worst.scenario} p95 ${worst.p95_ms} ms (budget ${worst.p95_budget_ms})` : "no perf run yet", "tile-perf"));
}

function trendSection(index) {
  const runs = index.slice(0, TREND_RUNS).reverse().map((r) => ({
    label: `${fmtShortDate(r.timestamp)} ${new Date(r.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`,
    title: `${r.id} · ${fmtDate(r.timestamp)}`,
    passRate: systemCounts(r).pass_rate,
    bugs: r.enabled_bugs,
    seconds: suiteSeconds(r),
  }));
  const colors = palette();
  const passCanvas = el("canvas", { "aria-label": "System-test pass rate per run", role: "img" });
  const durCanvas = el("canvas", { "aria-label": "Suite duration per run", role: "img" });

  const passTable = el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Run"), el("th", { class: "num" }, "Pass rate"), el("th", {}, "Bug switches"))),
    el("tbody", {}, runs.map((r) => el("tr", {}, el("td", {}, r.title), el("td", { class: "num" }, pct(r.passRate)), el("td", {}, r.bugs.join(", ") || "none")))));
  const durTable = el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Run"), SUITES.map((s) => el("th", { class: "num" }, `${s.label} (s)`)))),
    el("tbody", {}, runs.map((r) => el("tr", {}, el("td", {}, r.title), SUITES.map((s) => el("td", { class: "num" }, r.seconds[s.key] ?? "-"))))));

  const section = el("section", { class: "grid grid-2 section" },
    el("div", { class: "card", "data-testid": "pass-rate-chart" },
      el("h2", {}, "System-test pass rate"),
      legend([
        { label: "Runs without injected bugs", color: colors.series[0], shape: "line" },
        { label: "Runs with bug switches on (expected failures)", color: colors.series[1], shape: "dot" },
      ]),
      el("div", { class: "chart-box" }, passCanvas),
      el("details", { class: "table-view" }, el("summary", {}, "Show as table"), el("div", { class: "table-wrap" }, passTable))),
    el("div", { class: "card", "data-testid": "duration-chart" },
      el("h2", {}, "Suite duration per run"),
      legend(SUITES.map((s, i) => ({ label: s.label, color: colors.series[i] }))),
      el("div", { class: "chart-box" }, durCanvas),
      el("details", { class: "table-view" }, el("summary", {}, "Show as table"), el("div", { class: "table-wrap" }, durTable))));

  let charts = [];
  const draw = () => {
    if (!window.Chart) {
      // The CDN script failed (offline, blocked, or integrity mismatch): keep the data visible.
      for (const canvas of [passCanvas, durCanvas]) {
        canvas.parentElement.replaceChildren(el("p", { class: "empty" }, "Chart library unavailable. Use “Show as table” below."));
      }
      return;
    }
    charts = [passRateChart(passCanvas, runs, charts[0]), durationChart(durCanvas, runs, SUITES, charts[1])];
  };
  return { section, draw };
}

async function bugProofSection(index) {
  const bugRuns = index.filter((r) => r.enabled_bugs.length).slice(0, 10);
  if (!bugRuns.length) return null;
  const rows = [];
  for (const summary of bugRuns) {
    const run = await loadJSON(`data/runs/${encodeURIComponent(summary.id)}.json`);
    for (const bug of run.enabled_bugs) {
      // Live system tests only: unit tests assert the bug on purpose, and the in-runner API
      // backend never has bug switches on.
      const targeted = run.tests.filter((t) => SYSTEM_LAYERS.includes(t.layer) && t.bugs.includes(bug));
      const caught = targeted.filter((t) => t.status === "failed" || t.status === "error");
      const layers = [...new Set(caught.map((t) => LAYER_LABELS[t.layer]))].join(", ");
      rows.push(el("tr", {},
        el("td", {}, el("a", { href: `run.html?id=${encodeURIComponent(run.id)}&status=failed` }, fmtDate(run.timestamp))),
        el("td", {}, el("span", { class: "pill bug" }, bug)),
        el("td", { class: "num" }, `${caught.length} / ${targeted.length}`),
        el("td", {}, layers || "-"),
        el("td", {}, el("span", { class: `status ${caught.length ? "passed" : "failed"}` }, caught.length ? "Caught" : "Missed"))));
    }
  }
  return el("section", { class: "card section", "data-testid": "bug-proof" },
    el("h2", {}, "Injected bugs caught"),
    el("p", { class: "ink-2" }, "Runs with bug switches on. A switch is caught when the tests written to detect it fail."),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Run"), el("th", {}, "Bug switch"), el("th", { class: "num" }, "Targeted tests failed"), el("th", {}, "Caught by"), el("th", {}, "Verdict"))),
      el("tbody", {}, rows))));
}

function perfSection(index) {
  const run = index.find((r) => r.perf && r.perf.length);
  if (!run) return null;
  return el("section", { class: "card section", "data-testid": "perf-latest" },
    el("div", { class: "section-head" }, el("h2", {}, "Performance (latest perf run)"), el("span", { class: "muted" }, fmtDate(run.timestamp))),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Scenario"), el("th", { class: "num" }, "p95 (ms)"), el("th", { class: "num" }, "Budget (ms)"), el("th", {}, "Result"))),
      el("tbody", {}, run.perf.map((p) => el("tr", {},
        el("td", {}, p.scenario), el("td", { class: "num" }, p.p95_ms), el("td", { class: "num" }, p.p95_budget_ms),
        el("td", {}, statusBadge(p.passed ? "passed" : "failed"))))))));
}

async function main() {
  try {
    const index = await loadJSON("data/runs/index.json");
    if (!index.length) {
      app.replaceChildren(el("div", { class: "card empty" }, "No test runs have been published yet."));
      return;
    }
    const latest = index[0];
    const trend = trendSection(index);
    app.replaceChildren(
      el("h1", {}, "Test results"),
      el("p", { class: "ink-2" }, `${index.length} runs recorded. System tests (API, UI, perf) run against the deployed store; backend unit tests are shown separately.`),
      latestCard(latest),
      tiles(latest, index),
      trend.section,
    );
    trend.draw();
    onThemeChange(trend.draw);
    const perf = perfSection(index);
    if (perf) app.append(perf);
    const proof = await bugProofSection(index);
    if (proof) app.append(proof);
  } catch (error) {
    showError(app, error);
  }
}

main();
