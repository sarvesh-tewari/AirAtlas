import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { LayoutGrid } from "lucide-react";
import { EChart } from "./EChart";
import { chartTheme } from "../lib/chartTheme";
import { SectionTitle } from "./SectionTitle";
import { STANDARDS, type StandardId } from "../lib/standards";
import type { DailyRow } from "../lib/data";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function MonthlyHeatmap({ rows, standard, dark }: { rows: DailyRow[]; standard: StandardId; dark: boolean }) {
  const t = chartTheme(dark);
  const cfg = STANDARDS[standard];

  const { years, data, max } = useMemo(() => {
    const sums = new Map<string, { s: number; n: number }>(); // "year-month" -> avg
    const yearSet = new Set<string>();
    for (const r of rows) {
      const v = cfg.numeric ? (standard === "naqi" ? r.aqi_naqi : r.aqi_us)
        : (r.eu_band ? cfg.bands.findIndex((b) => b.label === r.eu_band) : null);
      if (v == null) continue;
      const yr = r.date.slice(0, 4), mo = +r.date.slice(5, 7) - 1;
      const key = `${yr}-${mo}`;
      yearSet.add(yr);
      const cur = sums.get(key) ?? { s: 0, n: 0 };
      cur.s += v; cur.n += 1; sums.set(key, cur);
    }
    const ys = [...yearSet].sort();
    const d: [number, number, number][] = [];
    let mx = cfg.numeric ? cfg.max : 5;
    for (const [key, { s, n }] of sums) {
      const [yr, mo] = key.split("-");
      d.push([+mo, ys.indexOf(yr), Math.round(s / n)]);
    }
    if (!cfg.numeric) mx = 5;
    return { years: ys, data: d, max: mx };
  }, [rows, standard, cfg]);

  const option = useMemo(() => {
    const pieces = cfg.numeric
      ? (() => { let lo = 0; return cfg.bands.map((b) => { const p = { min: lo, max: b.max ?? cfg.max, color: b.color }; lo = (b.max ?? cfg.max) + 1; return p; }); })()
      : cfg.bands.map((b, i) => ({ value: i, label: b.label, color: b.color }));
    return {
      grid: { left: 48, right: 12, top: 10, bottom: 24 },
      tooltip: { position: "top", backgroundColor: t.tooltipBg, borderWidth: 0, textStyle: { color: t.ink, fontSize: 12 },
        formatter: (p: { data: [number, number, number] }) => `${MONTHS[p.data[0]]} ${years[p.data[1]]}: ${p.data[2]}` },
      xAxis: { type: "category", data: MONTHS, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.label, fontSize: 10 }, splitArea: { show: false } },
      yAxis: { type: "category", data: years, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.label, fontSize: 11 } },
      visualMap: { type: "piecewise", show: false, pieces, dimension: 2, min: 0, max },
      series: [{ type: "heatmap", data, itemStyle: { borderColor: dark ? "#171a1f" : "#fff", borderWidth: 2 },
        label: { show: true, color: dark ? "#e8eaed" : "#17181b", fontSize: 10 } }],
    } as EChartsCoreOption;
  }, [data, years, max, cfg, t, dark]);

  return (
    <section className="card p-5">
      <div className="mb-3"><SectionTitle icon={LayoutGrid} color="#7c3aed" eyebrow="Seasonality" info="Average AQI per calendar month across all years, so seasonal patterns (e.g. winter peaks) stand out.">Monthly pattern</SectionTitle></div>
      {data.length ? <EChart option={option} height={Math.max(150, years.length * 42 + 60)} ariaLabel="Average AQI by month and year heatmap" />
        : <p className="py-8 text-center text-sm text-body">No data.</p>}
      <p className="mt-2 text-xs text-muted">Average {cfg.numeric ? "AQI" : "band"} per month, showing the seasonal pattern across years.</p>
    </section>
  );
}
