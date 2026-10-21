import { bugPills, el, fmtBytes, fmtDate, loadJSON, renderShell, runVerdict, showError, statusBadge } from "./common.js";

renderShell("downloads.html");
const app = document.getElementById("app");

const KINDS = [
  ["allure", "Allure report (zip)", "Unzip, then run allure open on the folder (opening index.html directly needs a local web server)."],
  ["junit", "JUnit XML (zip)", "Raw results for every suite, readable by any CI tool."],
  ["pdf", "PDF summary", "One page: results by layer, failures, perf and coverage."],
];

function link(file, label) {
  return file
    ? el("a", { href: file.path, download: "", "data-testid": "download-link" }, label, el("span", { class: "muted" }, ` · ${fmtBytes(file.bytes)}`))
    : el("span", { class: "muted" }, "-");
}

async function main() {
  try {
    const index = await loadJSON("data/runs/index.json");
    const withReports = index.filter((r) => Object.keys(r.reports).length);
    const summaryOnly = index.length - withReports.length;
    app.replaceChildren(
      el("h1", {}, "Downloads"),
      el("p", { class: "ink-2" }, "Reports for the newest 30 runs. Older runs keep their results on this site, but their report files are removed to keep the site small."),
      el("div", { class: "card table-wrap" }, el("table", { "data-testid": "downloads-table" },
        el("thead", {}, el("tr", {}, el("th", {}, "Run"), el("th", {}, "Result"), el("th", {}, "Bug switches"), KINDS.map(([, label, help]) => el("th", { title: help }, label)))),
        el("tbody", {}, withReports.map((r) => el("tr", { id: r.id, "data-testid": "download-row" },
          el("td", {}, el("a", { href: `run.html?id=${encodeURIComponent(r.id)}` }, fmtDate(r.timestamp)), el("div", { class: "muted mono" }, r.id)),
          el("td", {}, statusBadge(runVerdict(r))),
          el("td", {}, bugPills(r.enabled_bugs)),
          KINDS.map(([kind]) => el("td", {}, link(r.reports[kind], kind === "pdf" ? "summary.pdf" : `${kind}.zip`)))))))),
      el("ul", { class: "muted section" }, KINDS.map(([, label, help]) => el("li", {}, `${label}: ${help}`))),
      // replaceChildren() would print a null as the text "null", so only add this when needed.
      ...(summaryOnly ? [el("p", { class: "muted" }, `${summaryOnly} older runs have results only (reports expired).`)] : []));
    if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
  } catch (error) {
    showError(app, error);
  }
}

main();
