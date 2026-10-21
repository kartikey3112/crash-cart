"""One-page PDF summary of a run (fpdf2, built-in Helvetica, A4)."""

from pathlib import Path

from fpdf import FPDF

ACCENT = (228, 87, 46)
INK = (31, 36, 48)
MUTED = (107, 114, 128)
MAX_FAILURES = 12


def latin1(text: str) -> str:
    """Built-in PDF fonts only cover Latin-1; replace anything else so rendering never fails."""
    return text.encode("latin-1", "replace").decode("latin-1")


class SummaryPDF(FPDF):
    def heading(self, text: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*INK)
        self.cell(0, 6, latin1(text), new_x="LMARGIN", new_y="NEXT")

    def line_text(self, text: str, size: float = 9, color=INK, bold: bool = False) -> None:
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(*color)
        self.cell(0, 4.6, latin1(text)[:140], new_x="LMARGIN", new_y="NEXT")

    def table(self, header: list[str], rows: list[list[str]], widths: list[float]) -> None:
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(*MUTED)
        for text, width in zip(header, widths, strict=True):
            self.cell(width, 5, text)
        self.ln()
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*INK)
        for row in rows:
            for text, width in zip(row, widths, strict=True):
                self.cell(width, 4.6, latin1(str(text)))
            self.ln()


def render_summary(run: dict, out: Path, dashboard_url: str = "") -> int:
    """Write the PDF and return its page count (the layout is designed to fit on one)."""
    pdf = SummaryPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(14, 12, 14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 9, "CrashCart test run", new_x="LMARGIN", new_y="NEXT")
    counts = run["counts"]
    verdict = "PASSED" if counts["failed"] + counts["error"] == 0 else "FAILED"
    pdf.line_text(f"Run {run['id']}  |  {verdict}", 11, bold=True)
    pdf.line_text(
        f"{run['timestamp']}  |  commit {run['commit_sha'][:10]}  |  branch {run['branch']}  "
        f"|  trigger {run['trigger']}  |  duration {run['duration_s']}s",
        color=MUTED,
    )
    bugs = ", ".join(run["enabled_bugs"]) or "none"
    pdf.line_text(f"Bug switches enabled: {bugs}", color=ACCENT if run["enabled_bugs"] else MUTED)

    pdf.heading("Results by layer")
    rows = [
        [layer, c["total"], c["passed"], c["failed"] + c["error"], c["skipped"], c["flaky"],
         f"{c['pass_rate']}%" if c["pass_rate"] is not None else "-"]
        for layer, c in run["layers"].items()
    ]  # fmt: skip
    rows.append(
        ["all", counts["total"], counts["passed"], counts["failed"] + counts["error"],
         counts["skipped"], counts["flaky"], f"{counts['pass_rate']}%"]
    )  # fmt: skip
    pdf.table(
        ["Layer", "Total", "Passed", "Failed", "Skipped", "Flaky", "Pass rate"],
        rows,
        [30, 22, 22, 22, 22, 22, 30],
    )
    if run.get("coverage"):
        cov = run["coverage"]
        pdf.ln(1)
        pdf.line_text(
            f"Backend coverage: {cov['percent']}% "
            f"({cov['lines_covered']}/{cov['lines_total']} lines)",
            color=MUTED,
        )

    failures = [t for t in run["tests"] if t["status"] in ("failed", "error")]
    pdf.heading(f"Failed tests ({len(failures)})")
    if not failures:
        pdf.line_text("None.", color=MUTED)
    for test in failures[:MAX_FAILURES]:
        pdf.line_text(f"[{test['layer']}] {test['id']}", 8.5, bold=True)
        pdf.line_text(f"    {test['message'] or '(no message)'}", 8, color=MUTED)
    if len(failures) > MAX_FAILURES:
        pdf.line_text(f"... and {len(failures) - MAX_FAILURES} more (see the dashboard)", 8)

    flaky = [t for t in run["tests"] if t["status"] == "flaky"]
    if flaky:
        pdf.heading(f"Passed only on retry ({len(flaky)})")
        for test in flaky[:5]:
            pdf.line_text(test["id"], 8.5)

    if run["perf"]:
        pdf.heading("Performance (p95 vs budget)")
        pdf.table(
            ["Scenario", "Samples", "p50 ms", "p95 ms", "Budget ms", "Errors", "Result"],
            [
                [
                    p["scenario"],
                    p["samples"],
                    p["p50_ms"],
                    p["p95_ms"],
                    p["p95_budget_ms"],
                    p["errors"],
                    "pass" if p["passed"] else "FAIL",
                ]
                for p in run["perf"]
            ],  # fmt: skip
            [40, 22, 22, 22, 24, 20, 20],
        )

    pdf.ln(3)
    if dashboard_url:
        pdf.line_text(f"Full results: {dashboard_url}", 8.5, color=MUTED)
    pdf.line_text("CrashCart is a fictional demo store; all payments are fake.", 8, color=MUTED)

    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return pdf.page_no()
