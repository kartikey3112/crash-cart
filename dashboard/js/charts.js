// Chart.js helpers. Colors come from CSS custom properties so light/dark mode and the
// validated palette live in one place (dashboard.css). Thin marks, hairline grid, one axis.

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export function palette() {
  return {
    series: [css("--series-1"), css("--series-2"), css("--series-3"), css("--series-4")],
    surface: css("--surface"),
    grid: css("--grid"),
    axis: css("--axis"),
    muted: css("--muted"),
    ink2: css("--ink-2"),
  };
}

function baseOptions(colors) {
  const Chart = window.Chart;
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
  Chart.defaults.color = colors.muted;
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false }, // each chart has an HTML legend next to it
      tooltip: { padding: 10, boxPadding: 4, usePointStyle: true },
    },
    scales: {
      x: { grid: { display: false }, border: { color: colors.axis }, ticks: { maxRotation: 0, autoSkip: true } },
      y: { grid: { color: colors.grid }, border: { display: false } },
    },
  };
}

/** Re-draw when the visitor switches light/dark mode so colors stay validated. */
export function onThemeChange(redraw) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
}

/**
 * Pass-rate trend: a 2px line for runs WITHOUT injected bugs, plus separate markers for
 * runs with bug switches on (their failures are deliberate, so they aren't the trend).
 */
export function passRateChart(canvas, runs, existing) {
  existing?.destroy();
  const colors = palette();
  const labels = runs.map((r) => r.label);
  const clean = runs.map((r) => (r.bugs.length ? null : r.passRate));
  const bugged = runs.map((r) => (r.bugs.length ? r.passRate : null));
  const values = runs.map((r) => r.passRate).filter((v) => v !== null);
  const floor = values.length ? Math.max(0, Math.floor((Math.min(...values) - 2) / 5) * 5) : 0;
  const options = baseOptions(colors);
  options.scales.y.min = floor;
  options.scales.y.max = 100;
  options.scales.y.ticks = { callback: (v) => `${v}%` };
  options.plugins.tooltip.callbacks = {
    title: (items) => runs[items[0].dataIndex].title,
    label: (item) => `${item.dataset.label}: ${item.parsed.y}%`,
    afterBody: (items) => {
      const bugs = runs[items[0].dataIndex].bugs;
      return bugs.length ? `Bug switches: ${bugs.join(", ")}` : "";
    },
  };
  return new window.Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Pass rate (no bugs injected)",
          data: clean,
          spanGaps: true,
          borderColor: colors.series[0],
          backgroundColor: colors.series[0],
          borderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBorderColor: colors.surface,
          pointBorderWidth: 2,
        },
        {
          label: "Run with bug switches on",
          data: bugged,
          showLine: false,
          backgroundColor: colors.series[1],
          pointStyle: "rectRot",
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBorderColor: colors.surface,
          pointBorderWidth: 2,
        },
      ],
    },
    options,
  });
}

/** Suite duration per run as stacked columns (one categorical slot per suite, fixed order). */
export function durationChart(canvas, runs, suites, existing) {
  existing?.destroy();
  const colors = palette();
  const options = baseOptions(colors);
  options.scales.x.stacked = true;
  options.scales.y.stacked = true;
  options.scales.y.ticks = { callback: (v) => `${v}s` };
  options.plugins.tooltip.callbacks = {
    title: (items) => runs[items[0].dataIndex].title,
    label: (item) => `${item.dataset.label}: ${item.parsed.y ?? 0}s`,
  };
  return new window.Chart(canvas, {
    type: "bar",
    data: {
      labels: runs.map((r) => r.label),
      datasets: suites.map((suite, i) => ({
        label: suite.label,
        data: runs.map((r) => r.seconds[suite.key] ?? null),
        backgroundColor: colors.series[i],
        borderColor: colors.surface,
        borderWidth: { top: 2 }, // 2px surface gap between stacked segments
        borderSkipped: "bottom",
        maxBarThickness: 24,
      })),
    },
    options,
  });
}

/** HTML legend (identity is never color-alone; the table view carries every value). */
export function legend(items) {
  const wrap = document.createElement("div");
  wrap.className = "legend";
  for (const item of items) {
    const key = document.createElement("span");
    key.className = "key";
    const swatch = document.createElement("span");
    swatch.className = `swatch ${item.shape || ""}`;
    swatch.style.background = item.color;
    key.append(swatch, item.label);
    wrap.append(key);
  }
  return wrap;
}
